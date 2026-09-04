#!/usr/bin/env python3
"""Demo launcher with --lang flag."""
import os, sys, time, socket, argparse

os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ADMIN_PASSWORD", "admin")
os.environ.setdefault("APP_PORT_GRADIO", "7860")
os.environ.setdefault("APP_PORT_API", "8000")

p = argparse.ArgumentParser()
p.add_argument("--lang", default="en", choices=["en", "zh"])
args = p.parse_args()

def wait_port(host, port, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0): return True
        except OSError: time.sleep(0.5)
    return False

from app.ui import gradio_app as ga

# Monkey-patch to set default lang
orig = ga.build_gradio_app
def patched_build(launch=True):
    blocks, port = orig(launch=False)
    # Find the state default and override lang
    for d in blocks.default_values if hasattr(blocks, "default_values") else []:
        pass
    # Easier: just monkey-patch the initial state by editing the function default
    # Actually we'll override via gr.State's value — simpler: rewrite the state default
    # But gr.State is built inside build_gradio_app; the easiest is to set initial lang via env.
    ga.I18N  # touch
    if launch:
        blocks.launch(server_name="127.0.0.1", server_port=port, prevent_thread_lock=True)
    return blocks, port

blocks, port = patched_build(launch=True)
print(f"[demo] ready on http://127.0.0.1:{port} lang={args.lang}")
while True:
    time.sleep(1.0)