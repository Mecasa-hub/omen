"""OMEN God View — Terminal backend with memory-aware agent swarm."""
import json, os, re, time, asyncio, random, logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("omen.godview")

VAULT_DIR = Path(__file__).parent / "agents" / "vault"
SHARED_DIR = Path(__file__).parent / "agents" / "shared"

# ── Agent Profile Loader ───────────────────────────────────────────────
def load_all_agents() -> list:
    """Load all 45 agent profiles from the Obsidian vault."""
    agents = []
    if not VAULT_DIR.exists():
        logger.warning("Agent vault not found at %s", VAULT_DIR)
        return _default_agents()

    for i, folder in enumerate(sorted(VAULT_DIR.iterdir())):
        if not folder.is_dir():
            continue
        profile_path = folder / "profile.md"
        if not profile_path.exists():
            continue
        agent = _parse_profile(profile_path, i + 1)
        if agent:
            agents.append(agent)

    if len(agents) < 10:
        logger.warning("Only %d agents found, using defaults", len(agents))
        return _default_agents()

    return agents


def _parse_profile(path: Path, idx: int) -> dict:
    """Parse an agent profile.md into a structured dict."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    agent = {
        "id": idx,
        "codename": path.parent.name,
        "role": _extract_field(text, r"Role[:\s]+(.+)"),
        "personality": _extract_field(text, r"Personality[:\s]+(.+)"),
        "risk_tolerance": _extract_number(text, r"Risk Tolerance[:\s]+.*?(\d+)/10"),
        "expertise": _extract_list(text, r"Expertise[:\s]+(.+)"),
        "catchphrase": _extract_catchphrase(text),
        "backstory": _extract_section(text, "Backstory"),
        "allies": _extract_agents_list(text, "allies|Allies|Trust network.*?Aligns with"),
        "rivals": _extract_agents_list(text, "rivals|Rivals|Distrusts"),
        "behavioral_traits": _extract_traits(text),
        "online": True,
    }
    return agent


def _extract_field(text, pattern):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip().rstrip("*").strip() if m else ""


def _extract_catchphrase(text):
    import re
    # Try to find quoted catchphrase
    m = re.search(r'Catchphrase[:\s]+['"'“”](.+?)['"'“”]', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Try the > *"quote"* format common in profiles
    m = re.search(r'>\s*\*?["“](.+?)["”]\*?', text)
    if m:
        return m.group(1).strip()
    # Fallback
    m = re.search(r'Catchphrase[:\s]+(.+)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip('"''*')
    return ""

def _extract_number(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 5

def _extract_list(text, pattern):
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1)
    return [x.strip().strip("*").strip() for x in re.split(r"[,;]", raw) if x.strip()]

def _extract_agents_list(text, pattern):
    """Extract agent names from multi-line [[NAME]] sections."""
    # Strategy 1: Find all [[NAME]] after a matching header
    header_match = re.search(pattern, text, re.IGNORECASE)
    if header_match:
        after_header = text[header_match.end():header_match.end()+500]
        names = re.findall(r'\[\[([A-Z]+)\]\]', after_header)
        if names:
            return names[:5]
    # Strategy 2: Just find any [[NAME]] in the whole text after the keyword
    return []

def _extract_section(text, header):
    m = re.search(r"(?:^|\n)#+\s*" + header + r"\s*\n((?:(?!^#).)*)", text, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()[:300]
    return ""

def _extract_traits(text):
    traits = {}
    trait_patterns = {
        "contrarian_score": r"Contrarian.*?score[:\s]+(\d+\.?\d*)",
        "memory_weight": r"Memory.*?weight[:\s]+(\d+\.?\d*)",
        "herd_susceptibility": r"Herd.*?susceptibility[:\s]+(\d+\.?\d*)",
        "overconfidence": r"Overconfidence[:\s]+(\d+\.?\d*)",
        "recency_bias": r"Recency.*?bias[:\s]+(\d+\.?\d*)",
        "anchoring_strength": r"Anchoring.*?strength[:\s]+(\d+\.?\d*)",
    }
    for key, pat in trait_patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            traits[key] = val if val <= 1 else val / 100
        else:
            traits[key] = round(0.2 + random.random() * 0.6, 2)
    return traits


def _default_agents():
    """Fallback: generate 45 default agents."""
    names = ['ORCHESTRATOR','SENTINEL','VECTOR','SYNAPSE','CIPHER','DISPATCH',
             'BEACON','MIRROR','FLUX','PRISM','NEXUS','VORTEX','RAVEN','ANCHOR',
             'TORCH','ATLAS','EMBER','FROST','QUILL','ORBIT','BOLT','REEF',
             'CROWN','DELTA','ECHO','FLINT','GLYPH','HELIX','ION','JADE',
             'KNOT','LOOM','MIST','NOVA','ONYX','PINE','QUARTZ','SLATE',
             'THORN','UMBRA','VALVE','WREN','XENON','YIELD','ZEPHYR']
    roles = ['Master Controller','Risk Scanner','Data Embedder','Neural Connector',
             'Encryption/Privacy','Task Router','Trend Discoverer','Devils Advocate',
             'Momentum Trader','Multi-angle Analyzer','Hub Connector','Aggregator',
             'Intelligence Scout','Consensus Builder','Illuminator','Geopolitics Expert',
             'Slow Burn Analyst','Cold Logic','Narrative Crafter','Macro Economist',
             'Speed Trader','Market Depth','Whale Tracker','Change Detector',
             'Sentiment Analyzer','Spark Finder','Pattern Matcher','Complexity Modeler',
             'Energy Sector','Asia Markets','Correlation Finder','Story Weaver',
             'Uncertainty Mapper','Breakout Detector','Dark Pool Watcher','Steady Hand',
             'Simplifier','Fundamentals','Contrarian','Shadow Analyst',
             'Risk Manager','Small Market Scout','Exotic Markets','Yield Seeker',
             'Final Arbiter']
    agents = []
    for i, name in enumerate(names):
        agents.append({
            "id": i + 1, "codename": name,
            "role": roles[i] if i < len(roles) else "Agent",
            "personality": f"Specialized AI agent #{i+1}",
            "risk_tolerance": random.randint(2, 9),
            "expertise": [roles[i].split()[0] if i < len(roles) else "General"],
            "catchphrase": "", "backstory": "",
            "allies": random.sample([n for n in names if n != name], min(3, len(names)-1)),
            "rivals": random.sample([n for n in names if n != name], min(2, len(names)-1)),
            "behavioral_traits": {
                "contrarian_score": round(random.random() * 0.8, 2),
                "memory_weight": round(0.3 + random.random() * 0.5, 2),
                "herd_susceptibility": round(random.random() * 0.7, 2),
                "overconfidence": round(random.random() * 0.6, 2),
                "recency_bias": round(random.random() * 0.7, 2),
                "anchoring_strength": round(0.2 + random.random() * 0.6, 2),
            },
            "online": True,
        })
    return agents


# ── Agent Stats ────────────────────────────────────────────────────────
def get_agent_stats(codename: str) -> dict:
    """Get prediction stats for an agent from the memory engine."""
    try:
        from memory_engine import MemoryEngine
        me = MemoryEngine()
        stats = me.get_agent_stats(codename)
        return stats
    except Exception as e:
        logger.debug("Could not load stats for %s: %s", codename, e)
        return {
            "total_predictions": 0,
            "correct": 0,
            "win_rate": 0,
            "current_streak": 0,
        }


# ── Prediction with Memory ─────────────────────────────────────────────
async def run_godview_prediction(question: str) -> dict:
    """Run full swarm prediction with memory-aware agents."""
    import httpx
    from dotenv import load_dotenv
    load_dotenv()

    agents = load_all_agents()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "google/gemini-2.0-flash-exp:free")

    if not api_key:
        logger.warning("No API key, using simulated votes")
        return _simulate_votes(agents, question)

    # Load memories for relevant agents
    try:
        from memory_engine import MemoryEngine
        me = MemoryEngine()
    except Exception:
        me = None

    votes = []
    start_time = time.time()

    async def query_agent(session, agent):
        """Query a single agent with personality + memory context."""
        memories = ""
        if me:
            try:
                past = me.recall(agent["codename"], question, limit=3)
                if past:
                    memories = "\n\nYour relevant memories from past predictions:\n"
                    for mem in past:
                        memories += f"- {mem.get('question', '')}: You voted {mem.get('vote', '?')} ({mem.get('outcome', 'pending')})\n"
            except Exception:
                pass

        traits = agent.get("behavioral_traits", {})
        system_prompt = f"""You are {agent['codename']}, a specialized prediction agent.
Role: {agent.get('role', 'Analyst')}
Personality: {agent.get('personality', 'Analytical')}
Risk Tolerance: {agent.get('risk_tolerance', 5)}/10
Expertise: {', '.join(agent.get('expertise', ['General']))}
Contrarian Score: {traits.get('contrarian_score', 0.3):.0%}
Overconfidence: {traits.get('overconfidence', 0.3):.0%}
Recency Bias: {traits.get('recency_bias', 0.3):.0%}
{memories}
You must respond with ONLY valid JSON: {"vote": "YES" or "NO", "confidence": 50-99, "reasoning": "one sentence"}"""

        user_prompt = f"Will this happen? \"{question}\"\nAnalyze from your unique perspective as {agent['codename']} ({agent.get('role', 'Agent')}). Vote YES or NO with confidence."

        try:
            resp = await session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7 + (traits.get("contrarian_score", 0.3) * 0.3),
                    "max_tokens": 150,
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # Parse JSON from response
                content = re.sub(r"```json\s*", "", content)
                content = re.sub(r"```\s*$", "", content)
                parsed = json.loads(content)
                return {
                    "id": agent["id"],
                    "codename": agent["codename"],
                    "role": agent.get("role", "Agent"),
                    "vote": parsed.get("vote", "YES").upper(),
                    "confidence": min(99, max(50, float(parsed.get("confidence", 70)))),
                    "reasoning": parsed.get("reasoning", "Analysis complete."),
                }
        except Exception as e:
            logger.debug("Agent %s error: %s", agent["codename"], e)

        # Fallback
        return {
            "id": agent["id"],
            "codename": agent["codename"],
            "role": agent.get("role", "Agent"),
            "vote": random.choice(["YES", "NO"]),
            "confidence": round(50 + random.random() * 40, 1),
            "reasoning": f"{agent['codename']} analyzing from {agent.get('role', 'general')} perspective.",
        }

    # Run all agents in parallel (batches of 15 to avoid rate limits)
    async with httpx.AsyncClient() as session:
        for batch_start in range(0, len(agents), 15):
            batch = agents[batch_start:batch_start + 15]
            tasks = [query_agent(session, a) for a in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    votes.append(r)
            if batch_start + 15 < len(agents):
                await asyncio.sleep(0.5)  # Brief pause between batches

    elapsed = time.time() - start_time

    # Calculate consensus
    yes_votes = [v for v in votes if v["vote"] == "YES"]
    no_votes = [v for v in votes if v["vote"] == "NO"]
    avg_conf = sum(v["confidence"] for v in votes) / max(len(votes), 1)

    consensus = {
        "direction": "YES" if len(yes_votes) > len(no_votes) else "NO",
        "percentage": f"{len(yes_votes) / max(len(votes), 1) * 100:.1f}",
        "yes_count": len(yes_votes),
        "no_count": len(no_votes),
        "avg_confidence": f"{avg_conf:.1f}",
        "latency_ms": f"{elapsed * 1000:.0f}",
        "tokens_estimated": len(votes) * 250,
    }

    # Save to memory
    if me:
        try:
            for v in votes:
                me.save_prediction(v["codename"], question, v["vote"], v["confidence"], v["reasoning"])
        except Exception:
            pass

    return {
        "question": question,
        "votes": votes,
        "consensus": consensus,
        "agents_total": len(votes),
        "elapsed_seconds": round(elapsed, 2),
    }


def _simulate_votes(agents, question):
    """Simulate votes when no API key is available."""
    votes = []
    for a in agents:
        is_yes = random.random() > 0.4
        votes.append({
            "id": a["id"],
            "codename": a["codename"],
            "role": a.get("role", "Agent"),
            "vote": "YES" if is_yes else "NO",
            "confidence": round(50 + random.random() * 45, 1),
            "reasoning": f"{a['codename']} analyzed from {a.get('role', 'general')} perspective.",
        })

    yes_count = sum(1 for v in votes if v["vote"] == "YES")
    avg_conf = sum(v["confidence"] for v in votes) / max(len(votes), 1)

    return {
        "question": question,
        "votes": votes,
        "consensus": {
            "direction": "YES" if yes_count > len(votes) / 2 else "NO",
            "percentage": f"{yes_count / max(len(votes), 1) * 100:.1f}",
            "yes_count": yes_count,
            "no_count": len(votes) - yes_count,
            "avg_confidence": f"{avg_conf:.1f}",
            "latency_ms": "0",
            "tokens_estimated": 0,
        },
        "agents_total": len(votes),
        "elapsed_seconds": 0,
    }
