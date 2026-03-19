
import os
import json
import time
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

VAULT_DIR = Path(__file__).parent / "agents" / "vault"
SHARED_DIR = Path(__file__).parent / "agents" / "shared"
EXPERIMENTS_DIR = Path(__file__).parent / "agents" / "experiments"
DB_PATH = Path(__file__).parent / "data" / "omen.db"

# Ensure dirs exist
for d in [VAULT_DIR, SHARED_DIR, EXPERIMENTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class AgentMemory:
    """Manages persistent memory for a single OMEN agent.
    Obsidian-style markdown vault + SQLite for fast queries."""

    def __init__(self, codename: str):
        self.codename = codename
        self.vault_path = VAULT_DIR / codename
        self.memory_path = self.vault_path / "memory"
        self.profile_path = self.vault_path / "profile.md"
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self._profile_cache = None
        self._init_db()

    def _init_db(self):
        """Initialize SQLite tables for fast memory queries."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codename TEXT NOT NULL,
                question TEXT NOT NULL,
                vote TEXT,
                confidence REAL,
                reasoning TEXT,
                outcome TEXT,
                correct INTEGER,
                timestamp TEXT NOT NULL,
                market_id TEXT,
                allies_agreed TEXT,
                rivals_agreed TEXT,
                lesson TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codename TEXT NOT NULL,
                experiment_tag TEXT,
                trait_changed TEXT,
                old_value REAL,
                new_value REAL,
                predictions_before INTEGER,
                accuracy_before REAL,
                predictions_after INTEGER,
                accuracy_after REAL,
                status TEXT DEFAULT 'pending',
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_stats (
                codename TEXT PRIMARY KEY,
                total_predictions INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                calibration_score REAL DEFAULT 0.0,
                current_streak INTEGER DEFAULT 0,
                best_call TEXT,
                worst_call TEXT,
                last_updated TEXT
            )
        """)
        conn.commit()
        conn.close()

    def load_profile(self) -> dict:
        """Load agent profile from JSON (fast) or parse from markdown."""
        json_path = self.vault_path / "profile.json"
        if json_path.exists():
            with open(json_path) as f:
                return json.load(f)

        # Parse from full agent definitions
        defs_path = Path("/tmp/omen_agents_full.json")
        if defs_path.exists():
            with open(defs_path) as f:
                agents = json.load(f)
            for a in agents:
                if a["codename"] == self.codename:
                    # Cache as JSON for speed
                    with open(json_path, "w") as f:
                        json.dump(a, f, indent=2)
                    return a
        return {"codename": self.codename, "error": "profile not found"}

    def remember_prediction(self, question: str, vote: str, confidence: float,
                            reasoning: str, market_id: str = None,
                            allies_agreed: list = None, rivals_agreed: list = None):
        """Store a prediction in both SQLite and markdown vault."""
        now = datetime.now(timezone.utc).isoformat()

        # SQLite
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            INSERT INTO agent_memories (codename, question, vote, confidence,
                reasoning, timestamp, market_id, allies_agreed, rivals_agreed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.codename, question, vote, confidence, reasoning, now,
              market_id, json.dumps(allies_agreed or []),
              json.dumps(rivals_agreed or [])))
        conn.commit()
        conn.close()

        # Markdown memory note (Obsidian-style)
        date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_q = question[:50].replace("/", "-").replace(" ", "_").lower()
        filename = f"{date_tag}_{safe_q}.md"

        note = f"""# {question[:80]}
> Prediction by {self.codename} on {date_tag}

## My Analysis
- **Vote:** {vote}
- **Confidence:** {confidence:.1f}%
- **Market ID:** {market_id or "N/A"}

## Reasoning
{reasoning}

## Cross-links
- Allies who agreed: {allies_agreed or ["pending"]}
- Rivals who agreed: {rivals_agreed or ["pending"]}

## Outcome
- Result: *pending*
- Score: *pending*

## Learning
- *Will be updated when outcome is known*
"""
        with open(self.memory_path / filename, "w") as f:
            f.write(note)

        return filename

    def recall_similar(self, question: str, limit: int = 5) -> list:
        """Recall past predictions on similar topics."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        # Simple keyword matching (could be upgraded to vector search)
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        results = []
        for kw in keywords[:5]:
            rows = conn.execute("""
                SELECT * FROM agent_memories
                WHERE codename = ? AND question LIKE ?
                ORDER BY timestamp DESC LIMIT ?
            """, (self.codename, f"%{kw}%", limit)).fetchall()
            results.extend([dict(r) for r in rows])

        conn.close()
        # Deduplicate by id
        seen = set()
        unique = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        return unique[:limit]

    def get_stats(self) -> dict:
        """Get agent's prediction statistics."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM agent_stats WHERE codename = ?",
            (self.codename,)
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return {
            "codename": self.codename,
            "total_predictions": 0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "calibration_score": 0.0, "current_streak": 0
        }

    def record_outcome(self, question: str, actual_outcome: str):
        """Record the actual outcome and update stats."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # Find matching prediction
        row = conn.execute("""
            SELECT * FROM agent_memories
            WHERE codename = ? AND question LIKE ? AND outcome IS NULL
            ORDER BY timestamp DESC LIMIT 1
        """, (self.codename, f"%{question[:30]}%")).fetchone()

        if row:
            correct = 1 if row["vote"] and row["vote"].upper() == actual_outcome.upper() else 0
            lesson = self._generate_lesson(dict(row), actual_outcome, correct)

            conn.execute("""
                UPDATE agent_memories
                SET outcome = ?, correct = ?, lesson = ?
                WHERE id = ?
            """, (actual_outcome, correct, lesson, row["id"]))

            # Update stats
            stats = self.get_stats()
            total = stats["total_predictions"] + 1
            wins = stats["wins"] + (1 if correct else 0)
            losses = stats["losses"] + (0 if correct else 1)
            streak = (stats["current_streak"] + 1) if correct else 0

            conn.execute("""
                INSERT OR REPLACE INTO agent_stats
                (codename, total_predictions, wins, losses, win_rate,
                 calibration_score, current_streak, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.codename, total, wins, losses,
                  wins / total if total > 0 else 0,
                  self._calc_calibration(conn), streak,
                  datetime.now(timezone.utc).isoformat()))

            # Update markdown note
            self._update_memory_note(question, actual_outcome, correct, lesson)

        conn.commit()
        conn.close()

    def _generate_lesson(self, prediction: dict, outcome: str, correct: bool) -> str:
        """Generate a learning note from the outcome."""
        if correct:
            return f"Correctly predicted {outcome}. Confidence was {prediction.get('confidence', 0):.0f}%. Strategy validated."
        else:
            return f"Incorrectly predicted {prediction.get('vote', '?')} but outcome was {outcome}. Need to review reasoning and adjust approach."

    def _calc_calibration(self, conn) -> float:
        """Calculate Brier-style calibration score."""
        rows = conn.execute("""
            SELECT confidence, correct FROM agent_memories
            WHERE codename = ? AND correct IS NOT NULL
            ORDER BY timestamp DESC LIMIT 100
        """, (self.codename,)).fetchall()

        if not rows:
            return 0.0

        # Brier score: mean of (confidence/100 - actual)^2
        total = 0
        for r in rows:
            prob = (r[0] or 50) / 100.0
            actual = r[1] or 0
            total += (prob - actual) ** 2

        return 1.0 - (total / len(rows))  # Higher is better

    def _update_memory_note(self, question: str, outcome: str, correct: bool, lesson: str):
        """Update the markdown memory note with outcome."""
        date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_q = question[:50].replace("/", "-").replace(" ", "_").lower()
        filename = f"{date_tag}_{safe_q}.md"
        filepath = self.memory_path / filename

        if filepath.exists():
            content = filepath.read_text()
            content = content.replace(
                "- Result: *pending*",
                f"- Result: {outcome} {'✅' if correct else '❌'}"
            )
            content = content.replace(
                "- *Will be updated when outcome is known*",
                f"- {lesson}"
            )
            filepath.write_text(content)


class AutoResearchLoop:
    """Autoresearch-inspired self-improvement loop for agents.
    Instead of modifying train.py to lower val_bpb,
    agents modify their behavioral traits to improve prediction accuracy."""

    def __init__(self):
        self.experiments_log = EXPERIMENTS_DIR / "results.tsv"
        self._init_log()

    def _init_log(self):
        if not self.experiments_log.exists():
            with open(self.experiments_log, "w") as f:
                f.write("timestamp	codename	experiment	trait	old_val	new_val	accuracy_before	accuracy_after	status
")

    def propose_experiment(self, codename: str) -> dict:
        """Propose a trait modification experiment for an agent.
        Inspired by autoresearch's program.md loop."""
        mem = AgentMemory(codename)
        stats = mem.get_stats()
        profile = mem.load_profile()

        if stats["total_predictions"] < 5:
            return {"action": "skip", "reason": "Need at least 5 predictions to experiment"}

        traits = profile.get("behavioral_traits", {})
        win_rate = stats.get("win_rate", 0.5)

        # Analyze which trait to modify based on error patterns
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # Get recent wrong predictions
        wrong = conn.execute("""
            SELECT * FROM agent_memories
            WHERE codename = ? AND correct = 0
            ORDER BY timestamp DESC LIMIT 10
        """, (codename,)).fetchall()

        conn.close()

        if not wrong:
            return {"action": "skip", "reason": "No errors to learn from yet"}

        # Determine experiment based on error patterns
        experiment = self._diagnose_errors([dict(w) for w in wrong], traits, profile)
        return experiment

    def _diagnose_errors(self, errors: list, traits: dict, profile: dict) -> dict:
        """Diagnose error patterns and propose trait adjustments."""
        # Count overconfident errors (high confidence but wrong)
        overconfident_errors = sum(1 for e in errors if (e.get("confidence") or 50) > 70)
        herd_errors = 0  # TODO: track if agent followed herd when wrong

        experiment = {"action": "modify", "codename": profile.get("codename", "?")}

        if overconfident_errors > len(errors) * 0.6:
            # Too overconfident — reduce overconfidence
            old_val = traits.get("overconfidence", 0.5)
            new_val = max(0.0, old_val - 0.1)
            experiment.update({
                "trait": "overconfidence",
                "old_value": old_val,
                "new_value": new_val,
                "hypothesis": f"Reducing overconfidence from {old_val} to {new_val} because {overconfident_errors}/{len(errors)} errors were high-confidence"
            })
        elif traits.get("recency_bias", 0.5) > 0.6:
            # High recency bias might be causing whipsaw
            old_val = traits["recency_bias"]
            new_val = max(0.1, old_val - 0.15)
            experiment.update({
                "trait": "recency_bias",
                "old_value": old_val,
                "new_value": new_val,
                "hypothesis": f"Reducing recency bias from {old_val} to {new_val} to prevent overweighting recent events"
            })
        elif traits.get("herd_susceptibility", 0.3) > 0.4:
            old_val = traits["herd_susceptibility"]
            new_val = max(0.05, old_val - 0.15)
            experiment.update({
                "trait": "herd_susceptibility",
                "old_value": old_val,
                "new_value": new_val,
                "hypothesis": f"Reducing herd susceptibility from {old_val} to {new_val} to improve independent thinking"
            })
        else:
            # Try increasing memory weight to learn from history better
            old_val = traits.get("memory_weight", 0.5)
            new_val = min(1.0, old_val + 0.1)
            experiment.update({
                "trait": "memory_weight",
                "old_value": old_val,
                "new_value": new_val,
                "hypothesis": f"Increasing memory weight from {old_val} to {new_val} to better leverage past outcomes"
            })

        return experiment

    def apply_experiment(self, experiment: dict) -> bool:
        """Apply a trait modification to an agent's profile."""
        if experiment.get("action") != "modify":
            return False

        codename = experiment["codename"]
        trait = experiment["trait"]
        new_value = experiment["new_value"]

        # Update profile.json
        json_path = VAULT_DIR / codename / "profile.json"
        if json_path.exists():
            with open(json_path) as f:
                profile = json.load(f)
            profile["behavioral_traits"][trait] = new_value
            with open(json_path, "w") as f:
                json.dump(profile, f, indent=2)

        # Log experiment
        mem = AgentMemory(codename)
        stats = mem.get_stats()

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            INSERT INTO agent_experiments
            (codename, experiment_tag, trait_changed, old_value, new_value,
             predictions_before, accuracy_before, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """, (codename, f"exp_{int(time.time())}", trait,
              experiment["old_value"], new_value,
              stats["total_predictions"], stats["win_rate"],
              datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()

        # Log to TSV (autoresearch style)
        with open(self.experiments_log, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()}\t"
                    f"{codename}\t{experiment.get('hypothesis', '')}\t"
                    f"{trait}\t{experiment['old_value']}\t{new_value}\t"
                    f"{stats['win_rate']:.3f}\t\tactive\n")

        # Update evolution log in profile.md
        profile_md = VAULT_DIR / codename / "profile.md"
        if profile_md.exists():
            content = profile_md.read_text()
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            new_entry = f"| {date_str} | {trait}: {experiment['old_value']} → {new_value} | {experiment.get('hypothesis', 'auto-experiment')} |"
            content = content.replace(
                "| 2026-03-20 | Agent created | Initial personality profile |",
                f"| 2026-03-20 | Agent created | Initial personality profile |
{new_entry}"
            )
            profile_md.write_text(content)

        return True

    def evaluate_experiment(self, codename: str, experiment_id: int, min_predictions: int = 10) -> dict:
        """Evaluate if an experiment improved accuracy (autoresearch keep/discard logic)."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        exp = conn.execute(
            "SELECT * FROM agent_experiments WHERE id = ?",
            (experiment_id,)
        ).fetchone()

        if not exp:
            conn.close()
            return {"status": "not_found"}

        exp = dict(exp)

        # Count predictions since experiment
        since = conn.execute("""
            SELECT COUNT(*) as cnt,
                   SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END) as wins
            FROM agent_memories
            WHERE codename = ? AND timestamp > ?
            AND correct IS NOT NULL
        """, (codename, exp["timestamp"])).fetchone()

        conn.close()

        if since["cnt"] < min_predictions:
            return {"status": "insufficient_data", "predictions_since": since["cnt"]}

        accuracy_after = since["wins"] / since["cnt"] if since["cnt"] > 0 else 0
        accuracy_before = exp["accuracy_before"] or 0

        if accuracy_after > accuracy_before:
            status = "keep"
        elif accuracy_after == accuracy_before:
            status = "neutral"
        else:
            status = "discard"

        # Update experiment record
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            UPDATE agent_experiments
            SET predictions_after = ?, accuracy_after = ?, status = ?
            WHERE id = ?
        """, (since["cnt"], accuracy_after, status, experiment_id))
        conn.commit()
        conn.close()

        # If discard, revert the trait change
        if status == "discard":
            self._revert_experiment(exp)

        return {
            "status": status,
            "accuracy_before": accuracy_before,
            "accuracy_after": accuracy_after,
            "predictions_evaluated": since["cnt"]
        }

    def _revert_experiment(self, experiment: dict):
        """Revert a failed experiment (like git reset in autoresearch)."""
        codename = experiment["codename"]
        trait = experiment["trait_changed"]
        old_value = experiment["old_value"]

        json_path = VAULT_DIR / codename / "profile.json"
        if json_path.exists():
            with open(json_path) as f:
                profile = json.load(f)
            profile["behavioral_traits"][trait] = old_value
            with open(json_path, "w") as f:
                json.dump(profile, f, indent=2)


class SwarmMemoryManager:
    """Manages memories for the entire 45-agent swarm."""

    def __init__(self):
        self.agents = {}
        self.autoresearch = AutoResearchLoop()
        self._load_all_agents()

    def _load_all_agents(self):
        """Load all agent memory instances."""
        if VAULT_DIR.exists():
            for d in VAULT_DIR.iterdir():
                if d.is_dir() and (d / "profile.md").exists():
                    self.agents[d.name] = AgentMemory(d.name)

    def get_agent(self, codename: str) -> AgentMemory:
        if codename not in self.agents:
            self.agents[codename] = AgentMemory(codename)
        return self.agents[codename]

    def record_swarm_prediction(self, question: str, votes: list):
        """Record predictions from all agents in a swarm vote.
        votes: [{codename, vote, confidence, reasoning}, ...]"""
        for v in votes:
            agent = self.get_agent(v["codename"])
            # Determine allies/rivals agreement
            profile = agent.load_profile()
            allies = profile.get("allies", [])
            rivals = profile.get("rivals", [])
            allies_agreed = [x["codename"] for x in votes
                           if x["codename"] in allies and x["vote"] == v["vote"]]
            rivals_agreed = [x["codename"] for x in votes
                           if x["codename"] in rivals and x["vote"] == v["vote"]]
            agent.remember_prediction(
                question=question,
                vote=v["vote"],
                confidence=v["confidence"],
                reasoning=v["reasoning"],
                allies_agreed=allies_agreed,
                rivals_agreed=rivals_agreed
            )

    def record_outcome(self, question: str, outcome: str):
        """Record outcome for all agents and trigger autoresearch experiments."""
        for codename, agent in self.agents.items():
            agent.record_outcome(question, outcome)

        # After recording outcomes, check if any agents should experiment
        for codename in self.agents:
            exp = self.autoresearch.propose_experiment(codename)
            if exp.get("action") == "modify":
                self.autoresearch.apply_experiment(exp)

    def get_swarm_stats(self) -> list:
        """Get stats for all agents, sorted by win rate."""
        stats = []
        for codename, agent in self.agents.items():
            s = agent.get_stats()
            p = agent.load_profile()
            s["role"] = p.get("role", "")
            s["catchphrase"] = p.get("catchphrase", "")
            stats.append(s)
        return sorted(stats, key=lambda x: x.get("win_rate", 0), reverse=True)

    def build_context_for_agent(self, codename: str, question: str) -> str:
        """Build a rich context prompt for an agent including memories.
        This is injected into the LLM prompt so the agent "remembers"."""
        agent = self.get_agent(codename)
        profile = agent.load_profile()
        stats = agent.get_stats()
        memories = agent.recall_similar(question)

        context = f"""## Agent Profile: {codename}
Role: {profile.get('role', 'Unknown')}
Personality: {profile.get('personality', '')}
Catchphrase: "{profile.get('catchphrase', '')}"
Backstory: {profile.get('backstory', '')}
Risk Tolerance: {profile.get('risk_tolerance', 5)}/10
Expertise: {', '.join(profile.get('expertise', []))}

## Track Record
Predictions: {stats.get('total_predictions', 0)} | Win Rate: {stats.get('win_rate', 0):.1%} | Streak: {stats.get('current_streak', 0)}

## Behavioral Traits
"""
        traits = profile.get("behavioral_traits", {})
        for t, v in traits.items():
            context += f"- {t}: {v}
"

        if memories:
            context += "
## Relevant Past Predictions
"
            for m in memories[:3]:
                result = "✅" if m.get("correct") else "❌" if m.get("correct") is not None else "⏳"
                context += f"- {m.get('question', '?')[:60]}... → Voted {m.get('vote', '?')} ({m.get('confidence', 0):.0f}%) {result}
"
                if m.get("lesson"):
                    context += f"  Lesson: {m['lesson']}
"

        context += f"""
## Trust Network
Allies: {', '.join(profile.get('allies', []))}
Rivals: {', '.join(profile.get('rivals', []))}

## Instructions
You ARE {codename}. Stay in character. Your personality, biases, and expertise
should shape your analysis. Reference your past predictions when relevant.
Your catchphrase is: "{profile.get('catchphrase', '')}" — use it naturally.
"""
        return context


# Quick test
if __name__ == "__main__":
    smm = SwarmMemoryManager()
    print(f"Loaded {len(smm.agents)} agents")
    ctx = smm.build_context_for_agent("SENTINEL", "Will BTC hit 200k?")
    print(f"
Context length for SENTINEL: {len(ctx)} chars")
    print(ctx[:500])
