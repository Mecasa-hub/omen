"""MiroFish Bridge v2 — Proper integration with MiroFish backend.

MiroFish requires a multi-step pipeline:
1. Generate research document about the question (via Gemini)
2. Upload document to MiroFish ontology/generate (multipart form)
3. Build knowledge graph (async task)
4. Get graph data (nodes + edges)
5. Create simulation with entities
6. Prepare simulation (generate agent profiles)
7. Return graph + simulation data for Omen's D3 visualization
"""
import aiohttp
import asyncio
import logging
import json
import os
import time
import tempfile
from datetime import datetime

logger = logging.getLogger("omen.mirofish")

MIROFISH_URL = "http://localhost:5001"
GEMINI_URL = "https://openrouter.ai/api/v1/chat/completions"
# Load API key from .env file
def _load_api_key():
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('OPENROUTER_API_KEY='):
                        key = line.split('=', 1)[1].strip()
                        break
    return key

GEMINI_KEY = _load_api_key()
GEMINI_MODEL = "google/gemini-2.0-flash-001"


async def check_mirofish_health() -> bool:
    """Check if MiroFish backend is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MIROFISH_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
    except:
        return False


async def _generate_research_document(question: str) -> str:
    """Use Gemini to generate a research document about the prediction question."""
    prompt = f"""Write a comprehensive research brief (800-1200 words) analyzing this prediction market question:

"{question}"

Cover these aspects:
1. Background and context
2. Key entities involved (people, organizations, technologies, markets)
3. Arguments FOR the outcome happening
4. Arguments AGAINST the outcome happening  
5. Historical precedents and analogies
6. Key risk factors and uncertainties
7. Timeline considerations
8. Market sentiment indicators

Write as a factual research document with clear sections. Include specific names, dates, and data points where relevant."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GEMINI_URL,
                headers={"Authorization": f"Bearer {GEMINI_KEY}", "Content-Type": "application/json"},
                json={"model": GEMINI_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2000},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"Research document generation failed: {e}")
        return f"""# Research Analysis: {question}

## Background
This document provides a comprehensive analysis of the prediction market question: {question}

## Key Factors
The outcome depends on multiple interconnected factors:
- Market conditions and overall economic environment
- Regulatory developments across major jurisdictions
- Technological advancements and adoption rates
- Institutional investment flows and sentiment
- Historical precedents and cyclical patterns
- Geopolitical events and macroeconomic policies

## Arguments For
Proponents argue that growing adoption, limited supply dynamics, and increasing institutional interest could drive significant price appreciation within the given timeframe.

## Arguments Against
Skeptics point to regulatory uncertainty, market volatility, competition from alternative assets, and the difficulty of sustaining exponential growth at larger market capitalizations.

## Risk Assessment
Key risks include black swan events, regulatory crackdowns, technological vulnerabilities, and shifts in market sentiment. The probability distribution is highly uncertain with fat tails on both sides.

## Conclusion
The question requires careful analysis of multiple competing factors with significant uncertainty.
"""


async def _upload_ontology(session: aiohttp.ClientSession, question: str, research_text: str) -> dict:
    """Step 1: Upload research doc to MiroFish ontology/generate (multipart form)."""
    # Create temp file with research content
    tmp_path = tempfile.mktemp(suffix=".md", prefix="omen_research_")
    with open(tmp_path, "w") as f:
        f.write(f"# Research: {question}\n\n{research_text}")

    try:
        data = aiohttp.FormData()
        data.add_field("simulation_requirement", 
                       f"Simulate a prediction market debate about: {question}. "
                       f"Model different stakeholder perspectives, analyze evidence for and against, "
                       f"and predict the most likely outcome with confidence levels.")
        data.add_field("project_name", f"OMEN: {question[:60]}")
        data.add_field("additional_context", 
                       "This is for a prediction market oracle. Focus on entities that influence the outcome.")
        data.add_field("files", open(tmp_path, "rb"), filename="research.md", content_type="text/markdown")

        async with session.post(
            f"{MIROFISH_URL}/api/graph/ontology/generate",
            data=data,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            result = await resp.json()
            logger.info(f"MiroFish ontology response status={resp.status}: success={result.get("success")}")
            return result
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


async def _build_graph(session: aiohttp.ClientSession, project_id: str) -> dict:
    """Step 2: Build knowledge graph (async task)."""
    async with session.post(
        f"{MIROFISH_URL}/api/graph/build",
        json={"project_id": project_id},
        timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        result = await resp.json()
        logger.info(f"MiroFish graph build response: {result}")
        return result


async def _poll_task(session: aiohttp.ClientSession, task_id: str, max_wait: int = 180) -> dict:
    """Poll a MiroFish async task until completion."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            async with session.get(
                f"{MIROFISH_URL}/api/graph/task/{task_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                result = await resp.json()
                status = result.get("data", {}).get("status", "")
                progress = result.get("data", {}).get("progress", 0)
                logger.info(f"Task {task_id}: status={status}, progress={progress}%")

                if status in ("completed", "success", "done"):
                    return result
                elif status in ("failed", "error"):
                    raise Exception(f"Task failed: {result.get("data", {}).get("error", "unknown")}")
        except aiohttp.ClientError as e:
            logger.warning(f"Poll error: {e}")

        await asyncio.sleep(3)

    raise Exception(f"Task {task_id} timed out after {max_wait}s")


async def _get_graph_data(session: aiohttp.ClientSession, graph_id: str) -> dict:
    """Step 3: Get graph nodes and edges."""
    async with session.get(
        f"{MIROFISH_URL}/api/graph/data/{graph_id}",
        timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        result = await resp.json()
        return result.get("data", {})


async def _create_simulation(session: aiohttp.ClientSession, project_id: str, graph_id: str) -> dict:
    """Step 4: Create simulation."""
    async with session.post(
        f"{MIROFISH_URL}/api/simulation/create",
        json={"project_id": project_id, "graph_id": graph_id, "enable_twitter": True, "enable_reddit": True},
        timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        result = await resp.json()
        return result


async def _prepare_simulation(session: aiohttp.ClientSession, simulation_id: str) -> dict:
    """Step 5: Prepare simulation (generate agent profiles)."""
    async with session.post(
        f"{MIROFISH_URL}/api/simulation/prepare",
        json={"simulation_id": simulation_id},
        timeout=aiohttp.ClientTimeout(total=120)
    ) as resp:
        result = await resp.json()
        return result


async def _get_simulation_entities(session: aiohttp.ClientSession, graph_id: str) -> list:
    """Get entities from the graph for visualization."""
    try:
        async with session.get(
            f"{MIROFISH_URL}/api/simulation/entities/{graph_id}",
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            result = await resp.json()
            return result.get("data", {}).get("entities", [])
    except:
        return []


def _convert_graph_to_omen_format(graph_data: dict, entities: list, question: str) -> dict:
    """Convert MiroFish graph data to Omen's D3 visualization format."""
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    # Color palette for different entity types
    colors = ["#FF6B35", "#004E89", "#7B2D8E", "#1A936F", "#C5283D", 
              "#E9724C", "#3498db", "#9b59b6", "#27ae60", "#e74c3c"]

    # Map entity types to colors
    entity_types = list(set(n.get("type", "Unknown") for n in nodes))
    type_colors = {t: colors[i % len(colors)] for i, t in enumerate(entity_types)}

    swarm_agents = []
    for i, node in enumerate(nodes[:50]):  # Limit to 50 nodes
        node_type = node.get("type", "Entity")
        swarm_agents.append({
            "name": node.get("name", node.get("label", f"Entity_{i}")),
            "role": node_type,
            "category": node_type,
            "color": type_colors.get(node_type, "#999"),
            "vote": "YES" if i % 3 != 0 else "NO",  # Will be overridden by AI
            "confidence": 60 + (i * 7 % 30),
            "reasoning": node.get("description", node.get("properties", {}).get("description", "Knowledge graph entity")),
            "node_id": node.get("id", str(i)),
            "is_knowledge_graph": True
        })

    graph_edges = []
    for edge in edges[:100]:  # Limit edges
        graph_edges.append({
            "source": str(edge.get("source", edge.get("from", ""))),
            "target": str(edge.get("target", edge.get("to", ""))),
            "relation": edge.get("type", edge.get("label", "related_to")),
            "weight": edge.get("weight", 1.0)
        })

    return {
        "swarm_agents": swarm_agents,
        "graph_edges": graph_edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "entity_types": entity_types,
        "type_colors": type_colors,
        "graph_id": graph_data.get("graph_id", ""),
        "is_mirofish": True
    }


async def run_mirofish_prediction(question: str, mode: str = "fast") -> dict:
    """Run the MiroFish prediction pipeline.

    Modes:
      - 'fast': Ontology-only (~30s), 10-15 intelligent entity agents
      - 'deep': Full knowledge graph build (~3-5min), 30-50 nodes with relationships

    Returns graph data + agent results for Omen's D3 visualization.
    """
    logger.info(f"=== MiroFish Premium Pipeline START: {question[:80]} ===")
    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        # Health check
        try:
            async with session.get(f"{MIROFISH_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    raise Exception("MiroFish not available")
        except:
            raise Exception("MiroFish backend not running")

        # Step 1: Generate research document
        logger.info("Step 1: Generating research document...")
        research_text = await _generate_research_document(question)
        logger.info(f"Research doc generated: {len(research_text)} chars")

        # Step 2: Upload to MiroFish ontology/generate
        logger.info("Step 2: Uploading to MiroFish ontology/generate...")
        ontology_result = await _upload_ontology(session, question, research_text)

        if not ontology_result.get("success"):
            error = ontology_result.get("error", "Unknown ontology error")
            logger.error(f"Ontology generation failed: {error}")
            raise Exception(f"MiroFish ontology failed: {error}")

        project_id = ontology_result["data"]["project_id"]
        ontology = ontology_result["data"].get("ontology", {})
        entity_types = ontology.get("entity_types", [])
        edge_types = ontology.get("edge_types", [])
        logger.info(f"Ontology: project={project_id}, {len(entity_types)} entity types, {len(edge_types)} edge types")

        # Step 3: Build knowledge graph
        logger.info("Step 3: Building knowledge graph...")
        build_result = await _build_graph(session, project_id)

        graph_data = {"nodes": [], "edges": []}
        graph_id = ""
        entities = []

        if build_result.get("success"):
            task_id = build_result.get("data", {}).get("task_id", "")

            if task_id:
                # Poll for completion
                logger.info(f"Polling task {task_id}...")
                try:
                    graph_timeout = 300 if mode == "deep" else 30
                    task_result = await _poll_task(session, task_id, max_wait=graph_timeout)
                    # Get graph_id from project
                    async with session.get(f"{MIROFISH_URL}/api/graph/project/{project_id}") as resp:
                        proj_data = await resp.json()
                        graph_id = proj_data.get("data", {}).get("graph_id", "")

                    if graph_id:
                        graph_data = await _get_graph_data(session, graph_id)
                        entities = await _get_simulation_entities(session, graph_id)
                        logger.info(f"Graph built: {len(graph_data.get("nodes", []))} nodes, {len(graph_data.get("edges", []))} edges")
                except Exception as e:
                    if mode == "fast":
                        logger.info(f"Fast mode: Using ontology-only agents (graph build skipped/timed out)")
                    else:
                        logger.warning(f"Deep dive graph build incomplete: {e}. Using ontology-only mode.")
        else:
            logger.warning(f"Graph build failed: {build_result.get("error")}, using ontology-only mode")

        # Convert to Omen format
        omen_data = _convert_graph_to_omen_format(graph_data, entities, question)

        # If graph build failed, create nodes from ontology entity types
        if not omen_data["swarm_agents"]:
            logger.info("Falling back to ontology-based agents")
            for i, et in enumerate(entity_types):
                name = et.get("name", et.get("type", f"Type_{i}"))
                omen_data["swarm_agents"].append({
                    "name": name,
                    "role": et.get("description", "Knowledge entity"),
                    "category": "Ontology",
                    "color": ["#FF6B35", "#004E89", "#7B2D8E", "#1A936F", "#C5283D"][i % 5],
                    "vote": "YES" if i % 2 == 0 else "NO",
                    "confidence": 65,
                    "reasoning": et.get("description", f"Entity type from knowledge graph: {name}"),
                    "is_knowledge_graph": True
                })
            omen_data["node_count"] = len(entity_types)

        elapsed = time.time() - start_time
        logger.info(f"=== MiroFish Pipeline DONE in {elapsed:.1f}s: {omen_data["node_count"]} nodes ===")

        omen_data["project_id"] = project_id
        omen_data["graph_id"] = graph_id
        omen_data["pipeline_time_seconds"] = round(elapsed, 1)
        omen_data["research_text"] = research_text[:500]
        omen_data["mode"] = mode
        omen_data["ontology_summary"] = ontology_result["data"].get("analysis_summary", "")

        return omen_data
