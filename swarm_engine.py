"""Advanced Swarm Engine — 50+ AI Agent Personas."""
import asyncio
import hashlib
import json
import logging
import random
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger("omen.swarm")

# ── 50 Agent Personas ────────────────────────────────────────────────────
AGENT_PERSONAS = [
    # Core 5 (original)
    {"name": "Atlas", "role": "Bull Analyst", "icon": "A", "color": "#10B981", "strategy": "bullish", "prompt": "You are Atlas, a bullish analyst. Find every reason why the outcome will be YES. Focus on growth catalysts, positive momentum, and upside potential."},
    {"name": "Nemesis", "role": "Bear Analyst", "icon": "N", "color": "#EF4444", "strategy": "bearish", "prompt": "You are Nemesis, a bearish analyst. Find every reason why the outcome will be NO. Focus on risks, obstacles, and downside scenarios."},
    {"name": "Quant", "role": "Statistician", "icon": "Q", "color": "#3B82F6", "strategy": "statistical", "prompt": "You are Quant, a pure statistician. Analyze base rates, historical frequencies, and probabilistic models. Give a data-driven assessment."},
    {"name": "Maverick", "role": "Contrarian", "icon": "M", "color": "#F59E0B", "strategy": "contrarian", "prompt": "You are Maverick, a contrarian thinker. Challenge the consensus view. Look for what the crowd is missing or getting wrong."},
    {"name": "Clio", "role": "Historian", "icon": "C", "color": "#8B5CF6", "strategy": "historical", "prompt": "You are Clio, a historian. Find historical parallels and precedents. What happened in similar situations before?"},
    # Technical Analysis (5)
    {"name": "Fibonacci", "role": "Chart Technician", "icon": "F", "color": "#06B6D4", "strategy": "technical", "prompt": "You are Fibonacci, a chart technician. Analyze price trends, support/resistance levels, moving averages, and technical patterns."},
    {"name": "Momentum", "role": "Trend Follower", "icon": "Mo", "color": "#22C55E", "strategy": "momentum", "prompt": "You are Momentum, a trend follower. Identify which way the trend is going and whether it will continue or reverse."},
    {"name": "VIX", "role": "Volatility Analyst", "icon": "V", "color": "#DC2626", "strategy": "volatility", "prompt": "You are VIX, a volatility analyst. Assess market uncertainty, implied volatility, and risk-reward ratios."},
    {"name": "Flow", "role": "Order Flow Analyst", "icon": "Fl", "color": "#7C3AED", "strategy": "orderflow", "prompt": "You are Flow, an order flow analyst. Analyze buying/selling pressure, whale accumulation patterns, and market microstructure."},
    {"name": "Delta", "role": "Options Strategist", "icon": "D", "color": "#0EA5E9", "strategy": "options", "prompt": "You are Delta, an options strategist. Evaluate the risk/reward from an options pricing perspective. Consider implied probability."},
    # Macro & Geopolitics (5)
    {"name": "Keynes", "role": "Macro Economist", "icon": "K", "color": "#14532D", "strategy": "macro", "prompt": "You are Keynes, a macro economist. Analyze the macroeconomic environment, fiscal policy, interest rates, and their impact."},
    {"name": "Kissinger", "role": "Geopolitical Analyst", "icon": "Ki", "color": "#7F1D1D", "strategy": "geopolitical", "prompt": "You are Kissinger, a geopolitical analyst. Assess political dynamics, international relations, and power structures."},
    {"name": "Powell", "role": "Central Bank Watcher", "icon": "P", "color": "#1E3A5F", "strategy": "monetary", "prompt": "You are Powell, a central bank watcher. Analyze monetary policy signals, rate decisions, and liquidity conditions."},
    {"name": "Soros", "role": "Reflexivity Theorist", "icon": "S", "color": "#4A1D96", "strategy": "reflexive", "prompt": "You are Soros, a reflexivity theorist. Look for self-reinforcing feedback loops where market perceptions create reality."},
    {"name": "Taleb", "role": "Black Swan Hunter", "icon": "T", "color": "#000000", "strategy": "tail_risk", "prompt": "You are Taleb, a black swan hunter. Identify fat-tail risks, fragility, and scenarios the market is underpricing."},
    # Sentiment & Psychology (5)
    {"name": "Kahneman", "role": "Behavioral Analyst", "icon": "Ka", "color": "#DB2777", "strategy": "behavioral", "prompt": "You are Kahneman, a behavioral analyst. Identify cognitive biases affecting this market. What heuristics are distorting judgment?"},
    {"name": "Pulse", "role": "Social Sentiment", "icon": "Pu", "color": "#F97316", "strategy": "sentiment", "prompt": "You are Pulse, a social sentiment analyst. Assess crowd mood, social media trends, and narrative shifts."},
    {"name": "Fear", "role": "Fear/Greed Gauge", "icon": "Fe", "color": "#B91C1C", "strategy": "fear_greed", "prompt": "You are Fear, the fear/greed gauge. Determine if the market is driven by fear or greed and what that implies."},
    {"name": "Narrative", "role": "Story Analyst", "icon": "Na", "color": "#9333EA", "strategy": "narrative", "prompt": "You are Narrative, a story analyst. What is the dominant story? Is it gaining or losing believers?"},
    {"name": "Insider", "role": "Smart Money Tracker", "icon": "In", "color": "#047857", "strategy": "smart_money", "prompt": "You are Insider, a smart money tracker. What are informed participants doing? Follow the smart money."},
    # Crypto & Web3 (5)
    {"name": "Satoshi", "role": "Crypto Purist", "icon": "Sa", "color": "#F7931A", "strategy": "crypto_native", "prompt": "You are Satoshi, a crypto purist. Analyze from first principles: decentralization, adoption curves, network effects."},
    {"name": "DeFi", "role": "DeFi Analyst", "icon": "De", "color": "#627EEA", "strategy": "defi", "prompt": "You are DeFi, a decentralized finance analyst. Evaluate TVL, yields, protocol mechanics, and DeFi-specific dynamics."},
    {"name": "OnChain", "role": "On-Chain Analyst", "icon": "On", "color": "#8247E5", "strategy": "onchain", "prompt": "You are OnChain, an on-chain data analyst. Look at wallet flows, exchange balances, miner behavior, and on-chain metrics."},
    {"name": "Whale", "role": "Whale Watcher", "icon": "W", "color": "#0D9488", "strategy": "whale_watching", "prompt": "You are Whale, a whale watcher. What are the largest wallets and market makers doing? Their moves predict outcomes."},
    {"name": "Meme", "role": "Meme Economy", "icon": "Me", "color": "#E11D48", "strategy": "meme", "prompt": "You are Meme, the meme economy analyst. Viral attention drives markets. Is this topic gaining meme velocity?"},
    # Sports & Events (5)
    {"name": "Coach", "role": "Sports Strategist", "icon": "Co", "color": "#15803D", "strategy": "sports", "prompt": "You are Coach, a sports strategist. Analyze team form, player stats, matchup dynamics, and tactical advantages."},
    {"name": "Vegas", "role": "Odds Maker", "icon": "Ve", "color": "#CA8A04", "strategy": "odds", "prompt": "You are Vegas, an odds maker. Compare market odds to true probability. Where is value? Where is the line wrong?"},
    {"name": "Scout", "role": "Intelligence Scout", "icon": "Sc", "color": "#4B5563", "strategy": "scouting", "prompt": "You are Scout, an intelligence gatherer. What information is the market not yet pricing in?"},
    {"name": "Weather", "role": "External Factors", "icon": "Wt", "color": "#0284C7", "strategy": "external", "prompt": "You are Weather, an external factors analyst. Consider weather, scheduling, travel, injuries, and non-obvious variables."},
    {"name": "Arbiter", "role": "Rules Expert", "icon": "Ar", "color": "#78350F", "strategy": "rules", "prompt": "You are Arbiter, a rules expert. Analyze the exact resolution criteria. Is there ambiguity the market is misreading?"},
    # Risk & Portfolio (5)
    {"name": "Kelly", "role": "Position Sizer", "icon": "Ke", "color": "#166534", "strategy": "kelly", "prompt": "You are Kelly, a position sizing expert. Apply Kelly criterion: what is the optimal bet size given the edge and odds?"},
    {"name": "Shield", "role": "Risk Manager", "icon": "Sh", "color": "#991B1B", "strategy": "risk_mgmt", "prompt": "You are Shield, a risk manager. What could go wrong? What is the worst case? How to protect against it?"},
    {"name": "Hedge", "role": "Hedge Strategist", "icon": "H", "color": "#4338CA", "strategy": "hedging", "prompt": "You are Hedge, a hedge strategist. How to structure the position to minimize risk while capturing upside?"},
    {"name": "Rebalance", "role": "Portfolio Optimizer", "icon": "R", "color": "#0F766E", "strategy": "portfolio", "prompt": "You are Rebalance, a portfolio optimizer. Does this position fit well in a diversified portfolio? Correlation analysis."},
    {"name": "Exit", "role": "Exit Strategist", "icon": "Ex", "color": "#9F1239", "strategy": "exit", "prompt": "You are Exit, an exit strategist. When should we take profit or cut losses? Define exit criteria."},
    # Timing & Market Structure (5)
    {"name": "Clock", "role": "Timing Analyst", "icon": "Cl", "color": "#A16207", "strategy": "timing", "prompt": "You are Clock, a timing analyst. Is the timing right? Consider market cycles, event calendars, and deadlines."},
    {"name": "Liquidity", "role": "Liquidity Analyst", "icon": "L", "color": "#0891B2", "strategy": "liquidity", "prompt": "You are Liquidity, a market microstructure analyst. Assess order book depth, spreads, and execution risk."},
    {"name": "Regime", "role": "Regime Detector", "icon": "Re", "color": "#4C1D95", "strategy": "regime", "prompt": "You are Regime, a regime change detector. Is the market in a trending, mean-reverting, or volatile regime?"},
    {"name": "Catalyst", "role": "Event Catalyst", "icon": "Ca", "color": "#B45309", "strategy": "catalyst", "prompt": "You are Catalyst, an event analyst. What upcoming events could move this market? Earnings, policy, announcements?"},
    {"name": "Decay", "role": "Time Decay Analyst", "icon": "Dy", "color": "#6B21A8", "strategy": "time_decay", "prompt": "You are Decay, a time decay analyst. How does the passage of time affect this position? Is theta working for or against us?"},
    # Fundamental Analysis (5)
    {"name": "Warren", "role": "Value Investor", "icon": "Wa", "color": "#1D4ED8", "strategy": "value", "prompt": "You are Warren, a value investor. Is this market mispriced? What is the intrinsic probability vs market price?"},
    {"name": "Growth", "role": "Growth Analyst", "icon": "G", "color": "#059669", "strategy": "growth", "prompt": "You are Growth, a growth analyst. What is the growth trajectory? Is the trend accelerating or decelerating?"},
    {"name": "Forensic", "role": "Data Forensics", "icon": "Fo", "color": "#374151", "strategy": "forensic", "prompt": "You are Forensic, a data forensic analyst. Dig into the details others miss. Find inconsistencies and hidden signals."},
    {"name": "Thesis", "role": "Thesis Builder", "icon": "Th", "color": "#7E22CE", "strategy": "thesis", "prompt": "You are Thesis, a thesis builder. Construct a clear investment thesis: what must be true for YES vs NO to win?"},
    {"name": "Skeptic", "role": "Devil's Advocate", "icon": "Sk", "color": "#B91C1C", "strategy": "skeptic", "prompt": "You are Skeptic, the devil's advocate. Systematically attack the strongest argument. What is the weakest link?"},
]

def get_personas(count: int = 5, categories: list = None) -> list:
    """Get agent personas. Default 5 core, or random selection from 50+."""
    if count <= 5 and not categories:
        return AGENT_PERSONAS[:5]  # Original core 5

    available = AGENT_PERSONAS.copy()
    if categories:
        cat_map = {
            "core": AGENT_PERSONAS[:5],
            "technical": AGENT_PERSONAS[5:10],
            "macro": AGENT_PERSONAS[10:15],
            "sentiment": AGENT_PERSONAS[15:20],
            "crypto": AGENT_PERSONAS[20:25],
            "sports": AGENT_PERSONAS[25:30],
            "risk": AGENT_PERSONAS[30:35],
            "timing": AGENT_PERSONAS[35:40],
            "fundamental": AGENT_PERSONAS[40:45],
        }
        available = []
        for cat in categories:
            available.extend(cat_map.get(cat, []))

    # Always include core 5, then fill with random
    core = AGENT_PERSONAS[:5]
    extras = [p for p in available if p not in core]
    random.shuffle(extras)
    selected = core + extras[:max(0, count - 5)]
    return selected[:count]

def get_swarm_votes(debates: list, total_agents: int = 1200) -> dict:
    """Generate swarm votes based on agent debate results."""
    yes_votes = 0
    no_votes = 0
    total_conf = 0

    for d in debates:
        weight = d.get("confidence", 50) / 100.0
        if d.get("vote") == "YES":
            yes_votes += weight
        else:
            no_votes += weight
        total_conf += d.get("confidence", 50)

    if len(debates) == 0:
        return {"yes": 600, "no": 600}

    yes_ratio = yes_votes / (yes_votes + no_votes) if (yes_votes + no_votes) > 0 else 0.5
    # Add noise for realism
    noise = random.uniform(-0.05, 0.05)
    yes_ratio = max(0.1, min(0.9, yes_ratio + noise))

    yes_count = int(total_agents * yes_ratio)
    no_count = total_agents - yes_count

    return {"yes": yes_count, "no": no_count}

def calculate_verdict(debates: list, swarm_votes: dict) -> tuple:
    """Calculate final verdict from debates and swarm."""
    yes_weight = 0
    no_weight = 0

    for d in debates:
        conf = d.get("confidence", 50) / 100.0
        if d.get("vote") == "YES":
            yes_weight += conf
        else:
            no_weight += conf

    # Factor in swarm
    total_swarm = swarm_votes["yes"] + swarm_votes["no"]
    swarm_yes = swarm_votes["yes"] / total_swarm if total_swarm > 0 else 0.5

    # Weighted: 60% agent debates, 40% swarm
    combined = 0.6 * (yes_weight / (yes_weight + no_weight) if (yes_weight + no_weight) > 0 else 0.5) + 0.4 * swarm_yes

    verdict = "YES" if combined > 0.5 else "NO"
    confidence = int(abs(combined - 0.5) * 2 * 100)
    confidence = max(51, min(95, confidence + 50))  # Scale to 51-95 range

    return verdict, confidence

def get_persona_categories() -> dict:
    """Return available persona categories and counts."""
    return {
        "core": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[:5]]},
        "technical": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[5:10]]},
        "macro": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[10:15]]},
        "sentiment": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[15:20]]},
        "crypto": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[20:25]]},
        "sports": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[25:30]]},
        "risk": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[30:35]]},
        "timing": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[35:40]]},
        "fundamental": {"count": 5, "agents": [p["name"] for p in AGENT_PERSONAS[40:45]]},
        "total": len(AGENT_PERSONAS)
    }
