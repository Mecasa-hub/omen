#!/usr/bin/env python3
"""MiroFish Health Watchdog
Checks MiroFish health and restarts if down.
Also cleans up old projects to prevent accumulation.
"""
import subprocess
import json
import time
import os
import sys
from datetime import datetime, timedelta

MIROFISH_DIR = "/a0/usr/workdir/MiroFish/backend"
MIROFISH_URL = "http://localhost:5001"
LOG_FILE = "/tmp/mirofish_watchdog.log"
MAX_PROJECTS = 20
PROJECT_MAX_AGE_HOURS = 48

def log(msg):
    ts = datetime.now(tz=__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def check_health():
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             f"{MIROFISH_URL}/health"],
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip() == "200"
    except Exception:
        return False

def check_process():
    r = subprocess.run(["pgrep", "-f", "MiroFish.*run.py"], capture_output=True, text=True)
    return bool(r.stdout.strip())

def restart_mirofish():
    log("RESTARTING MiroFish...")
    subprocess.run(["pkill", "-f", "MiroFish.*run.py"], capture_output=True)
    time.sleep(2)

    env = os.environ.copy()
    env_path = "/a0/usr/workdir/MiroFish/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()

    subprocess.Popen(
        [f"{MIROFISH_DIR}/.venv/bin/python", "run.py"],
        cwd=MIROFISH_DIR,
        env=env,
        stdout=open("/tmp/mirofish_stdout.log", "a"),
        stderr=open("/tmp/mirofish_stderr.log", "a"),
        start_new_session=True
    )

    time.sleep(5)
    if check_health():
        log("MiroFish restarted successfully")
        return True
    else:
        log("MiroFish restart FAILED")
        return False

def cleanup_old_projects():
    try:
        r = subprocess.run(
            ["curl", "-s", f"{MIROFISH_URL}/api/graph/project/list"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(r.stdout)
        projects = data.get("data", [])

        if len(projects) <= MAX_PROJECTS:
            return

        log(f"Cleaning up: {len(projects)} projects (max {MAX_PROJECTS})")
        cutoff = datetime.now(tz=__import__("datetime").timezone.utc) - timedelta(hours=PROJECT_MAX_AGE_HOURS)

        deleted = 0
        for p in projects:
            created_str = p.get("created_at", "")
            if not created_str:
                continue
            try:
                created = datetime.fromisoformat(created_str.replace("Z", ""))
                if created < cutoff:
                    pid = p.get("id", p.get("project_id", ""))
                    if pid:
                        subprocess.run(
                            ["curl", "-s", "-X", "DELETE",
                             f"{MIROFISH_URL}/api/graph/project/{pid}"],
                            capture_output=True, text=True, timeout=10
                        )
                        deleted += 1
            except Exception:
                pass

        if deleted:
            log(f"Deleted {deleted} old projects")
    except Exception as e:
        log(f"Cleanup error: {e}")

def main():
    healthy = check_health()
    process = check_process()

    if healthy:
        log(f"MiroFish OK (health=200, process={'up' if process else 'unknown'})")
    else:
        log(f"MiroFish DOWN (health=fail, process={'up' if process else 'down'})")
        restart_mirofish()

    cleanup_old_projects()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        log("Starting MiroFish watchdog daemon (check every 60s)")
        while True:
            try:
                main()
            except Exception as e:
                log(f"Watchdog error: {e}")
            time.sleep(60)
    else:
        main()
