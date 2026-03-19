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

async def _generate_research_context(question: str) -> str:
    """Generate comprehensive research briefing for agents using Gemini."""
    import httpx
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "google/gemini-2.0-flash-001")

    if not api_key:
        return f"Research analysis of: {question}"

    research_prompt = f"""Write a concise research brief (400-500 words) analyzing this prediction market question:

"{question}"

Cover:
1. Background and context with specific names and dates
2. Key entities involved (people, organizations, technologies, markets)
3. Arguments FOR the outcome (with evidence)
4. Arguments AGAINST the outcome (with evidence)
5. Historical precedents and analogies
6. Key risk factors and wildcards
7. Timeline considerations
8. Current market sentiment and positioning

Write as a factual research analyst. Use specific data points, dates, and statistics."""

    try:
        async with httpx.AsyncClient() as session:
            resp = await session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": research_prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.3,
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content:
                    logger.info("Research context generated: %d chars", len(content))
                    return content
    except Exception as e:
        logger.warning("Research generation failed: %s", e)

    return f"Research analysis of: {question}. Analyze market conditions, regulatory environment, technological factors, and historical precedents."


async def _query_single_agent(session, agent, question, research_context, api_key, model, round_num=1, previous_votes=None):
    """Query a single agent with full personality + research context."""
    codename = agent.get("codename", "UNKNOWN")
    role = agent.get("role", "Analyst")
    personality = agent.get("personality", "Analytical")
    risk = agent.get("risk_tolerance", 5)
    expertise = agent.get("expertise", ["General"])
    backstory = agent.get("backstory", "")
    traits = agent.get("behavioral_traits", {})
    debate_style = agent.get("debate_style", "balanced")
    sig_phrases = agent.get("signature_phrases", [])

    # Build expertise string safely
    if isinstance(expertise, list):
        exp_str = ", ".join(str(e).strip("- ") for e in expertise[:5])
    else:
        exp_str = str(expertise)

    contrarian = float(traits.get("contrarian_score", 0.3))
    overconf = float(traits.get("overconfidence", 0.3))
    recency = float(traits.get("recency_bias", 0.3))
    herd = float(traits.get("herd_susceptibility", 0.3))

    # Build round-specific context
    round_context = ""
    if round_num == 2 and previous_votes:
        yes_count = sum(1 for v in previous_votes if v.get("vote") == "YES")
        no_count = sum(1 for v in previous_votes if v.get("vote") == "NO")
        notable = []
        for v in previous_votes[:10]:
            if v.get("codename") != codename:
                notable.append(f"  - {v['codename']} ({v.get('role','')}): {v['vote']} {v.get('confidence',0):.0f}% - {v.get('reasoning','')[:60]}")
        round_context = f"""

ROUND 2 - DEBATE PHASE:
You've seen the initial swarm results: {yes_count} YES / {no_count} NO
Notable positions from other agents:
{chr(10).join(notable[:6])}

Now reconsider. You may change your vote or double down. Factor in what others said.
If you're contrarian, challenge the majority. If you follow herds, align with consensus."""
    elif round_num == 3 and previous_votes:
        yes_count = sum(1 for v in previous_votes if v.get("vote") == "YES")
        no_count = sum(1 for v in previous_votes if v.get("vote") == "NO")
        round_context = f"""

FINAL ROUND - LOCK IN:
After debate, the swarm stands at {yes_count} YES / {no_count} NO.
This is your FINAL vote. Commit fully based on all evidence and debate."""

    system_prompt = f"""You are {codename}, a specialized prediction market agent.

ROLE: {role}
PERSONALITY: {personality}
RISK TOLERANCE: {risk}/10 ({"aggressive" if risk > 7 else "moderate" if risk > 4 else "conservative"})
EXPERTISE: {exp_str}
DEBATE STYLE: {debate_style}

COGNITIVE BIASES:
- Contrarian tendency: {contrarian*100:.0f}%
- Overconfidence: {overconf*100:.0f}%
- Recency bias: {recency*100:.0f}%
- Herd susceptibility: {herd*100:.0f}%

{f"BACKSTORY: " + backstory[:200] if backstory else ""}

RESEARCH BRIEFING (read carefully before voting):
{research_context[:800]}
{round_context}

STAY IN CHARACTER. Use your unique perspective, biases, and expertise.
Respond with ONLY valid JSON: {{"vote": "YES" or "NO", "confidence": 50-99, "reasoning": "one sentence in your voice"}}"""

    user_prompt = f"""PREDICTION MARKET: "{question}"
Round {round_num}/3. Vote as {codename}."""

    try:
        resp = await session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": min(1.2, 0.6 + contrarian * 0.5 + (risk / 10) * 0.2),
                "max_tokens": 150,
            },
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"```json\s*", "", content)
            content = re.sub(r"```\s*$", "", content)
            content = re.sub(r"^[^{]*", "", content)
            content = re.sub(r"[^}]*$", "", content)
            if not content:
                raise ValueError("Empty")
            parsed = json.loads(content)
            return {
                "id": agent.get("id", 0),
                "codename": codename,
                "role": role,
                "vote": str(parsed.get("vote", "YES")).upper().strip(),
                "confidence": min(99, max(50, float(parsed.get("confidence", 70)))),
                "reasoning": str(parsed.get("reasoning", "Analysis complete."))[:200],
                "personality": str(personality)[:60],
                "risk_tolerance": risk,
                "round": round_num,
            }
        else:
            logger.warning("%s R%d: HTTP %s", codename, round_num, resp.status_code)
    except Exception as e:
        logger.debug("%s R%d: %s", codename, round_num, e)

    # Personality-influenced fallback
    is_yes = random.random() > (0.3 + contrarian * 0.3)
    return {
        "id": agent.get("id", 0),
        "codename": codename,
        "role": role,
        "vote": "YES" if is_yes else "NO",
        "confidence": round(55 + risk * 3 + random.random() * 20, 1),
        "reasoning": f"{codename} analyzing from {role} perspective.",
        "personality": str(personality)[:60],
        "risk_tolerance": risk,
        "round": round_num,
    }


def _form_factions(votes):
    """Cluster agents into factions based on vote + confidence."""
    yes_high = [v for v in votes if v["vote"] == "YES" and v["confidence"] >= 75]
    yes_low = [v for v in votes if v["vote"] == "YES" and v["confidence"] < 75]
    no_high = [v for v in votes if v["vote"] == "NO" and v["confidence"] >= 75]
    no_low = [v for v in votes if v["vote"] == "NO" and v["confidence"] < 75]

    factions = []
    if yes_high:
        factions.append({
            "name": "Strong Bulls",
            "stance": "YES",
            "strength": "high",
            "members": [v["codename"] for v in yes_high],
            "count": len(yes_high),
            "avg_confidence": round(sum(v["confidence"] for v in yes_high) / len(yes_high), 1),
            "leader": max(yes_high, key=lambda v: v["confidence"])["codename"],
        })
    if yes_low:
        factions.append({
            "name": "Cautious Bulls",
            "stance": "YES",
            "strength": "low",
            "members": [v["codename"] for v in yes_low],
            "count": len(yes_low),
            "avg_confidence": round(sum(v["confidence"] for v in yes_low) / len(yes_low), 1),
            "leader": max(yes_low, key=lambda v: v["confidence"])["codename"],
        })
    if no_high:
        factions.append({
            "name": "Strong Bears",
            "stance": "NO",
            "strength": "high",
            "members": [v["codename"] for v in no_high],
            "count": len(no_high),
            "avg_confidence": round(sum(v["confidence"] for v in no_high) / len(no_high), 1),
            "leader": max(no_high, key=lambda v: v["confidence"])["codename"],
        })
    if no_low:
        factions.append({
            "name": "Cautious Bears",
            "stance": "NO",
            "strength": "low",
            "members": [v["codename"] for v in no_low],
            "count": len(no_low),
            "avg_confidence": round(sum(v["confidence"] for v in no_low) / len(no_low), 1),
            "leader": max(no_low, key=lambda v: v["confidence"])["codename"],
        })
    return factions


async def _run_batch(session, agents, question, research, api_key, model, round_num, prev_votes=None):
    """Run a batch of agents in parallel (batches of 15)."""
    votes = []
    for batch_start in range(0, len(agents), 15):
        batch = agents[batch_start:batch_start + 15]
        tasks = [
            _query_single_agent(session, a, question, research, api_key, model, round_num, prev_votes)
            for a in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict):
                votes.append(r)
            elif isinstance(r, Exception):
                logger.debug("Batch exception: %s", r)
        if batch_start + 15 < len(agents):
            await asyncio.sleep(0.3)
    return votes


async def run_godview_prediction(question: str) -> dict:
    """Run full research-informed multi-round swarm prediction.

    Phase 1: Generate research context via Gemini
    Phase 2: Round 1 - Initial independent votes (45 agents)
    Phase 3: Round 2 - Debate round (agents see Round 1 results, top 15 re-vote)
    Phase 4: Faction formation + consensus calculation
    """
    import httpx
    from dotenv import load_dotenv
    load_dotenv()

    agents = load_all_agents()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "google/gemini-2.0-flash-001")

    if not api_key:
        logger.warning("No API key, using simulated votes")
        return _simulate_votes(agents, question)

    start_time = time.time()
    rounds_data = []

    # ── Phase 1: Research Context ────────────────────────────
    logger.info("God View: Generating research context...")
    research = await _generate_research_context(question)
    research_time = time.time() - start_time

    # ── Phase 2: Round 1 - All 45 agents vote independently ──
    logger.info("God View: Round 1 — %d agents voting...", len(agents))
    async with httpx.AsyncClient() as session:
        round1_votes = await _run_batch(session, agents, question, research, api_key, model, round_num=1)

    round1_yes = sum(1 for v in round1_votes if v["vote"] == "YES")
    round1_no = len(round1_votes) - round1_yes
    rounds_data.append({
        "round": 1,
        "name": "Initial Vote",
        "yes": round1_yes,
        "no": round1_no,
        "total": len(round1_votes),
    })

    # ── Phase 3: Round 2 - Debate (top 15 most confident re-vote) ──
    logger.info("God View: Round 2 — Debate phase...")
    # Select top 15 most impactful agents for debate (mix of YES and NO)
    sorted_by_conf = sorted(round1_votes, key=lambda v: v["confidence"], reverse=True)
    debate_agents_names = set(v["codename"] for v in sorted_by_conf[:15])
    debate_agents = [a for a in agents if a["codename"] in debate_agents_names]

    async with httpx.AsyncClient() as session:
        round2_votes = await _run_batch(
            session, debate_agents, question, research, api_key, model,
            round_num=2, prev_votes=round1_votes
        )

    # Merge round 2 votes into round 1 (override for agents who re-voted)
    final_votes = {v["codename"]: v for v in round1_votes}
    vote_changes = []
    for v2 in round2_votes:
        old = final_votes.get(v2["codename"], {})
        if old.get("vote") != v2["vote"]:
            vote_changes.append({
                "codename": v2["codename"],
                "from": old.get("vote", "?"),
                "to": v2["vote"],
                "reason": v2.get("reasoning", "")[:100],
            })
        final_votes[v2["codename"]] = v2

    all_votes = list(final_votes.values())
    round2_yes = sum(1 for v in all_votes if v["vote"] == "YES")
    round2_no = len(all_votes) - round2_yes
    rounds_data.append({
        "round": 2,
        "name": "Debate",
        "yes": round2_yes,
        "no": round2_no,
        "total": len(all_votes),
        "changes": len(vote_changes),
    })

    # ── Phase 4: Faction Formation ────────────────────────────
    factions = _form_factions(all_votes)

    elapsed = time.time() - start_time

    # Calculate final consensus
    yes_votes = [v for v in all_votes if v["vote"] == "YES"]
    no_votes = [v for v in all_votes if v["vote"] == "NO"]
    total = max(len(all_votes), 1)
    avg_conf = sum(v["confidence"] for v in all_votes) / total

    consensus = {
        "direction": "YES" if len(yes_votes) > len(no_votes) else "NO",
        "percentage": f"{len(yes_votes) / total * 100:.1f}",
        "yes_count": len(yes_votes),
        "no_count": len(no_votes),
        "avg_confidence": f"{avg_conf:.1f}",
        "latency_ms": f"{elapsed * 1000:.0f}",
        "tokens_estimated": (len(round1_votes) + len(round2_votes)) * 350,
    }

    # Save to memory (if available)
    try:
        from memory_engine import MemoryEngine
        me = MemoryEngine()
        for v in all_votes:
            me.save_prediction(v["codename"], question, v["vote"], v["confidence"], v["reasoning"])
    except Exception:
        pass

    return {
        "question": question,
        "votes": all_votes,
        "consensus": consensus,
        "agents_total": len(all_votes),
        "elapsed_seconds": round(elapsed, 2),
        "research_context": research[:500],
        "research_time_ms": round(research_time * 1000),
        "rounds": rounds_data,
        "factions": factions,
        "vote_changes": vote_changes,
        "debate_agents": len(debate_agents),
    }


def _simulate_votes(agents, question):
    """Fallback: simulate votes when no API key is available."""
    votes = []
    for a in agents:
        traits = a.get("behavioral_traits", {})
        contrarian = float(traits.get("contrarian_score", 0.3))
        risk = a.get("risk_tolerance", 5)
        is_yes = random.random() > (0.3 + contrarian * 0.3)
        base_conf = 55 + risk * 3
        votes.append({
            "id": a.get("id", 0),
            "codename": a["codename"],
            "role": a.get("role", "Agent"),
            "vote": "YES" if is_yes else "NO",
            "confidence": round(base_conf + random.random() * 20, 1),
            "reasoning": f"{a["codename"]} analyzed from {a.get("role", "general")} perspective.",
            "personality": str(a.get("personality", ""))[:60],
            "risk_tolerance": risk,
            "round": 1,
        })

    factions = _form_factions(votes)
    yes_count = sum(1 for v in votes if v["vote"] == "YES")
    avg_conf = sum(v["confidence"] for v in votes) / max(len(votes), 1)

    return {
        "question": question,
        "votes": votes,
        "consensus": {
            "direction": "YES" if yes_count > len(votes) // 2 else "NO",
            "percentage": f"{yes_count / max(len(votes), 1) * 100:.1f}",
            "yes_count": yes_count,
            "no_count": len(votes) - yes_count,
            "avg_confidence": f"{avg_conf:.1f}",
            "latency_ms": "50",
            "tokens_estimated": 0,
        },
        "agents_total": len(votes),
        "elapsed_seconds": 0.05,
        "research_context": "",
        "research_time_ms": 0,
        "rounds": [{"round": 1, "name": "Simulated", "yes": yes_count, "no": len(votes) - yes_count, "total": len(votes)}],
        "factions": factions,
        "vote_changes": [],
        "debate_agents": 0,
    }
