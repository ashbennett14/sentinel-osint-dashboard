#!/usr/bin/env python3
"""Start SENTINEL as a detached, self-healing local service."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_DIR / "backend"
FRONTEND_DIR = PROJECT_DIR / "frontend"
LOG_DIR = PROJECT_DIR / "logs"
PYTHON = BACKEND_DIR / "venv" / "bin" / "python"
PID_FILE = LOG_DIR / "sentinel-supervisor.pid"


def _running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _detach() -> bool:
    """Double-fork; return True only in the detached supervisor process."""
    first = os.fork()
    if first > 0:
        return False
    os.setsid()
    second = os.fork()
    if second > 0:
        os._exit(0)
    return True


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            existing = int(PID_FILE.read_text().strip())
            if _running(existing):
                return 0
        except (ValueError, OSError):
            pass

    if not PYTHON.exists():
        print(f"Python runtime not found: {PYTHON}", file=sys.stderr)
        return 1

    if not _detach():
        return 0

    os.chdir(PROJECT_DIR)
    os.umask(0o022)
    supervisor_log = open(LOG_DIR / "supervisor.log", "a", buffering=1)
    sys.stdout = supervisor_log
    sys.stderr = supervisor_log
    PID_FILE.write_text(str(os.getpid()))

    specs = {
        "backend": ([str(PYTHON), "run.py"], BACKEND_DIR, LOG_DIR / "backend.log", LOG_DIR / "backend.err.log"),
        "frontend": ([str(PYTHON), "-m", "http.server", "8080"], FRONTEND_DIR, LOG_DIR / "frontend.log", LOG_DIR / "frontend.err.log"),
    }
    children = {}
    running = True

    def stop(_signum=None, _frame=None):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def launch(name):
        command, cwd, stdout_path, stderr_path = specs[name]
        stdout = open(stdout_path, "a", buffering=1)
        stderr = open(stderr_path, "a", buffering=1)
        children[name] = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr)
        print(f"Started {name} pid={children[name].pid}")

    try:
        for name in specs:
            launch(name)
        while running:
            for name in specs:
                child = children.get(name)
                if child and child.poll() is not None:
                    print(f"Restarting {name} after exit={child.returncode}")
                    time.sleep(1)
                    launch(name)
            time.sleep(2)
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
        for child in children.values():
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
        PID_FILE.unlink(missing_ok=True)
        supervisor_log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
