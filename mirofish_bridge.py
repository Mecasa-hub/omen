"""MiroFish Bridge — connects Omen to MiroFish backend for premium predictions."""
import aiohttp
import asyncio
import logging
import json

logger = logging.getLogger("omen.mirofish")

MIROFISH_URL = "http://localhost:5001"

async def check_mirofish_health() -> bool:
    """Check if MiroFish backend is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MIROFISH_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
    except:
        return False

async def run_mirofish_prediction(question: str) -> dict:
    """Run a full MiroFish prediction cycle.
    1. Build knowledge graph from the question context
    2. Run multi-agent simulation
    3. Return graph data + agent results
    """
    async with aiohttp.ClientSession() as session:
        # Check health first
        try:
            async with session.get(f"{MIROFISH_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    raise Exception("MiroFish not available")
        except:
            raise Exception("MiroFish backend not running")

        # Step 1: Generate ontology from the question
        ontology_payload = {
            "text": f"Prediction market question: {question}. Analyze all factors, entities, relationships, and potential outcomes.",
            "simulation_goal": f"Predict the outcome of: {question}"
        }

        try:
            async with session.post(
                f"{MIROFISH_URL}/api/graph/ontology/generate",
                json=ontology_payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                ontology_data = await resp.json()
                logger.info(f"MiroFish ontology generated: {len(ontology_data.get('entity_types', []))} entity types")
        except Exception as e:
            logger.error(f"MiroFish ontology failed: {e}")
            raise

        # Step 2: Build knowledge graph
        try:
            graph_payload = {
                "ontology": ontology_data,
                "text": f"Prediction market analysis for: {question}"
            }
            async with session.post(
                f"{MIROFISH_URL}/api/graph/build",
                json=graph_payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                graph_data = await resp.json()
                graph_id = graph_data.get("graph_id", "")
                logger.info(f"MiroFish graph built: {graph_id}")
        except Exception as e:
            logger.error(f"MiroFish graph build failed: {e}")
            raise

        # Step 3: Get graph nodes and edges
        try:
            async with session.get(
                f"{MIROFISH_URL}/api/graph/data/{graph_id}",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                full_graph = await resp.json()
        except Exception as e:
            logger.error(f"MiroFish graph data failed: {e}")
            full_graph = {"nodes": [], "edges": []}

        # Step 4: Run simulation
        sim_id = None
        sim_results = {}
        try:
            sim_payload = {
                "graph_id": graph_id,
                "goal": f"Predict: {question}",
                "rounds": 3
            }
            async with session.post(
                f"{MIROFISH_URL}/api/simulation/create",
                json=sim_payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                sim_data = await resp.json()
                sim_id = sim_data.get("simulation_id", "")

            # Start simulation
            async with session.post(
                f"{MIROFISH_URL}/api/simulation/start",
                json={"simulation_id": sim_id},
                timeout=aiohttp.ClientTimeout(total=180)
            ) as resp:
                sim_results = await resp.json()
        except Exception as e:
            logger.error(f"MiroFish simulation failed: {e}")
            sim_results = {}

        # Step 5: Format results for Omen's D3 graph
        nodes = full_graph.get("nodes", [])
        edges = full_graph.get("edges", [])

        # Convert MiroFish graph format to Omen swarm_agents format
        swarm_agents = []
        entity_colors = {
            'Person': '#FF6B35', 'Organization': '#004E89', 'Event': '#7B2D8E',
            'Policy': '#1A936F', 'Market': '#C5283D', 'Technology': '#E9724C',
            'Risk': '#3498db', 'Trend': '#9b59b6', 'Factor': '#27ae60'
        }

        for node in nodes:
            entity_type = node.get("entity_type", "Entity")
            swarm_agents.append({
                "name": node.get("name", "Unknown"),
                "role": entity_type,
                "icon": node.get("name", "?")[0],
                "color": entity_colors.get(entity_type, "#666"),
                "strategy": "mirofish",
                "category": entity_type,
                "vote": "YES",
                "confidence": 70,
                "reasoning": node.get("summary", f"MiroFish entity: {node.get('name')}"),
                "ai_generated": True,
                "mirofish": True,
                "properties": node.get("attributes", {}),
                "uuid": node.get("uuid", ""),
            })

        # Format edges for D3
        graph_edges = []
        for edge in edges:
            graph_edges.append({
                "source": edge.get("source_name", ""),
                "target": edge.get("target_name", ""),
                "type": edge.get("edge_type", "related"),
                "fact": edge.get("fact", ""),
            })

        return {
            "swarm_agents": swarm_agents,
            "graph_edges": graph_edges,
            "graph_id": graph_id,
            "simulation_id": sim_id if sim_results else None,
            "simulation_results": sim_results,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "tier": "premium",
        }
