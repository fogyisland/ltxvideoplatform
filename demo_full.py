#!/usr/bin/env python3
"""Full-app demo launcher. Uses subprocess for uvicorn so it survives alongside
Gradio. Real inference still needs CUDA + LTX-Video; this is for UI / auth /
admin flow demos on non-GPU hosts.

NOT for production. Use `python -m app.main` on a GPU host.
"""
import os
import sys
import time
import socket
import subprocess

os.environ["LTX_ALLOW_NO_CUDA"] = "1"
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ADMIN_PASSWORD", "admin")
os.environ.setdefault("APP_PORT_API", "8000")
os.environ.setdefault("APP_PORT_GRADIO", "7860")

def wait_port(host, port, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0): return True
        except OSError: time.sleep(0.5)
    return False


# Bootstrap the DB / dirs / seed admin (in this process)
from app.main import _bootstrap, build_gradio_app
_bootstrap()
print(f"[demo] DB bootstrapped (admin user seeded if missing).")


# Launch uvicorn in a subprocess (more stable than in-process thread)
api_log_path = os.path.join(os.environ.get("TEMP", "C:\\Windows\\Temp"), "ltx_api.log")
api_proc = subprocess.Popen(
    [sys.executable, "-c",
     "import os; os.environ['LTX_ALLOW_NO_CUDA']='1'; "
     "import uvicorn; from app.main import build_app; "
     f"uvicorn.run(build_app(), host='127.0.0.1', port={os.environ['APP_PORT_API']}, log_level='warning')"],
    stdout=open(api_log_path, "w"), stderr=subprocess.STDOUT,
)
print(f"[demo] API log: {api_log_path}")
if not wait_port("127.0.0.1", int(os.environ["APP_PORT_API"]), 30):
    print("[demo] API did not bind", file=sys.stderr)
    api_proc.terminate(); sys.exit(1)
print(f"[demo] API on http://127.0.0.1:{os.environ['APP_PORT_API']}")


# Launch Gradio (blocks main thread but prevent_thread_lock=True)
try:
    print(f"[demo] Launching Gradio on http://127.0.0.1:{os.environ['APP_PORT_GRADIO']}")
    build_gradio_app(launch=True)
finally:
    api_proc.terminate()
    api_proc.wait(timeout=5)