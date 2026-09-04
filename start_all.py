#!/usr/bin/env python3
"""One-command launcher for the LTX-Video Web Platform.

Starts both services in the background and waits for them to be ready:

  - FastAPI backend on :8000  (LTX-Video inference + REST API)
  - Next.js frontend on :3380 (browser UI; talks to backend)

Usage:
    python start_all.py                # start both
    python start_all.py --stop         # stop both
    python start_all.py --status       # show status
    python start_all.py --logs api     # tail the API log
    python start_all.py --logs web     # tail the web log
    python start_all.py --no-gpu       # start API in UI-only demo mode (no CUDA)

Logs are written to .run/api.log and /tmp/next_3380.log.
PID files are in .run/.
"""
import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_DIR = ROOT / ".run"
RUN_DIR.mkdir(exist_ok=True)

API_PIDFILE = RUN_DIR / "api.pid"
WEB_PIDFILE = RUN_DIR / "web.pid"
API_LOG = RUN_DIR / "api.log"
WEB_LOG = Path(os.environ.get("TEMP", "/tmp")) / "next_3380.log"

API_PORT = 3381
WEB_PORT = 3380


def port_listening(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_listening(host, port):
            return True
        time.sleep(0.3)
    return False


def pid_alive(pidfile: Path) -> int | None:
    """Cross-platform check: is the PID in pidfile still a running process?"""
    if not pidfile.exists():
        return None
    try:
        pid = int(pidfile.read_text().strip())
    except (ValueError, OSError):
        pidfile.unlink(missing_ok=True)
        return None
    # Best-effort: try psutil-style check via subprocess (Windows-safe)
    try:
        if sys.platform == "win32":
            # tasklist filters by PID; non-zero exit means no such process
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=2,
            )
            if str(pid) in r.stdout:
                return pid
            pidfile.unlink(missing_ok=True)
            return None
        else:
            os.kill(pid, 0)
            return pid
    except Exception:
        pidfile.unlink(missing_ok=True)
        return None


def start_api(no_gpu: bool) -> int:
    pid = pid_alive(API_PIDFILE)
    if pid is not None:
        print(f"[api] already running (pid {pid})")
        return pid
    env = os.environ.copy()
    env["JWT_SECRET"] = env.get("JWT_SECRET", "x" * 32)
    env["APP_PORT_API"] = str(API_PORT)
    if no_gpu:
        env["LTX_ALLOW_NO_CUDA"] = "1"
    log = open(API_LOG, "ab")
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import os; "
         f"os.environ['APP_PORT_API']='{API_PORT}'; "
         "import uvicorn; from app.main import build_app; "
         f"uvicorn.run(build_app(), host='127.0.0.1', port={API_PORT}, log_level='info')"],
        cwd=str(ROOT),
        env=env,
        stdout=log, stderr=log,
    )
    API_PIDFILE.write_text(str(proc.pid))
    print(f"[api] starting (pid {proc.pid})...")
    if wait_for_port("127.0.0.1", API_PORT, timeout=30):
        print(f"[api] ready on http://127.0.0.1:{API_PORT}")
    else:
        print(f"[api] did not bind within 30s; see {API_LOG}")
    return proc.pid


def start_web() -> int:
    pid = pid_alive(WEB_PIDFILE)
    frontend_dir = ROOT / "frontend"
    env_local = frontend_dir / ".env.local"
    next_dir = frontend_dir / ".next"
    env_local_mtime = env_local.stat().st_mtime if env_local.exists() else 0
    next_mtime = next_dir.stat().st_mtime if next_dir.exists() else 0
    needs_build = (
        not next_dir.exists() or
        (env_local.exists() and env_local_mtime > next_mtime) or
        # config files / sources affect build
        any(
            (frontend_dir / f).stat().st_mtime > next_mtime
            for f in ("package.json", "next.config.ts", "tsconfig.json", "tailwind.config.ts")
            if (frontend_dir / f).exists()
        )
    )
    if pid is not None:
        if needs_build:
            print(f"[web] running (pid {pid}) but .env.local or config changed -> restarting")
            stop_pidfile(WEB_PIDFILE, "web")
            pid = None
        else:
            print(f"[web] already running (pid {pid})")
            return pid
    if needs_build:
        print("[web] building...")
        r = subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), shell=True)
        if r.returncode != 0:
            print(f"[web] build failed (exit {r.returncode})")
            return -1
    log = open(WEB_LOG, "ab")
    proc = subprocess.Popen(
        ["npm", "start"], cwd=str(frontend_dir),
        env=os.environ.copy(), stdout=log, stderr=log, shell=True,
    )
    WEB_PIDFILE.write_text(str(proc.pid))
    print(f"[web] starting (pid {proc.pid})...")
    if wait_for_port("127.0.0.1", WEB_PORT, timeout=30):
        print(f"[web] ready on http://127.0.0.1:{WEB_PORT}")
    else:
        print(f"[web] did not bind within 30s; see {WEB_LOG}")
    return proc.pid


def stop_pidfile(pidfile: Path, name: str):
    pid = pid_alive(pidfile)
    if pid is None:
        print(f"[{name}] not running")
        return
    try:
        # Windows-friendly: send Ctrl+C via taskkill
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       check=False, capture_output=True)
        pidfile.unlink(missing_ok=True)
        print(f"[{name}] stopped (pid {pid})")
    except Exception as e:
        print(f"[{name}] error stopping pid {pid}: {e}")


def status():
    api = pid_alive(API_PIDFILE)
    web = pid_alive(WEB_PIDFILE)
    api_up = port_listening("127.0.0.1", API_PORT)
    web_up = port_listening("127.0.0.1", WEB_PORT)
    print(f"[api] pid={api} listening={api_up} port={API_PORT}")
    print(f"[web] pid={web} listening={web_up} port={WEB_PORT}")


def tail_log(path: Path, lines: int = 50):
    if not path.exists():
        print(f"(no log at {path})")
        return
    data = path.read_bytes()[-8192:]
    text = data.decode("utf-8", errors="replace")
    print(f"--- last {lines} lines of {path} ---")
    print(text)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stop", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--logs", choices=["api", "web"])
    p.add_argument("--no-gpu", action="store_true", help="start API in UI-only demo mode")
    p.add_argument("--web-only", action="store_true", help="only start the web frontend")
    p.add_argument("--api-only", action="store_true", help="only start the API")
    args = p.parse_args()

    if args.stop:
        stop_pidfile(API_PIDFILE, "api")
        stop_pidfile(WEB_PIDFILE, "web")
        return
    if args.status:
        status(); return
    if args.logs == "api":
        tail_log(API_LOG); return
    if args.logs == "web":
        tail_log(WEB_LOG); return

    if not args.web_only:
        start_api(args.no_gpu)
    if not args.api_only:
        start_web()
    print()
    print("Services:")
    status()
    print()
    print(f"Open: http://127.0.0.1:{WEB_PORT}")
    print(f"  sign in: raymond.xu / Admin909217 (admin)")
    print(f"Logs: {API_LOG}  and  {WEB_LOG}")
    print(f"Stop: python {Path(__file__).name} --stop")


if __name__ == "__main__":
    main()