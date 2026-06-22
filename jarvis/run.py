#!/usr/bin/env python3
"""MITRA Web Application Launcher.

Starts the FastAPI backend via uvicorn CLI (not main.py directly, which
would block before uvicorn has a chance to bind the socket), waits for the
health endpoint, then opens the dashboard in Chrome.

Usage:
    cd jarvis/
    python3 run.py
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

_PORT       = 8001
_HEALTH_URL = f"http://localhost:{_PORT}/health"
_DASH_URL   = f"http://localhost:{_PORT}"
_JARVIS_DIR = Path(__file__).resolve().parent


def _kill_existing() -> None:
    """Kill any process already bound to port 8001."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{_PORT}"],
            capture_output=True, text=True,
        )
        pids = result.stdout.strip()
        if pids:
            print(f"Found existing process(es) on port {_PORT} — terminating…")
            subprocess.run(f"kill -9 {pids}", shell=True, check=False)  # noqa: S602
            time.sleep(1)
        else:
            print(f"No existing process on port {_PORT}.")
    except Exception as exc:
        print(f"Port check skipped: {exc}")


def _wait_for_server(retries: int = 15, delay: float = 1.0) -> bool:
    """Poll the health endpoint until the server responds."""
    import urllib.request
    import urllib.error

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(_HEALTH_URL, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        print(f"  Waiting for server… ({attempt}/{retries})")
        time.sleep(delay)
    return False


def main() -> None:
    print("=" * 60)
    print("  MITRA Web Application Launcher")
    print("=" * 60)

    # 1. Kill any lingering process
    print("\n[1/4] Checking port 8001…")
    _kill_existing()

    # 2. Start uvicorn via CLI — this is the correct way to start uvicorn
    #    programmatically; calling `python3 main.py` passes through uvicorn.run()
    #    which blocks before the socket is ready.
    print("\n[2/4] Starting MITRA backend via uvicorn…")
    print(f"  Dashboard → {_DASH_URL}")

    server_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", str(_PORT),
            "--log-level", "info",
        ],
        cwd=str(_JARVIS_DIR),
    )

    # 3. Wait for the health endpoint
    print("\n[3/4] Waiting for server to be ready…")
    if not _wait_for_server(retries=20, delay=0.8):
        print("\n✗ Server did not start in time.")
        server_proc.terminate()
        sys.exit(1)
    print("✓ Server is online.")

    # 4. Open browser
    print("\n[4/4] Opening browser…")
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    try:
        if Path(chrome_bin).exists():
            subprocess.Popen([chrome_bin, _DASH_URL])
            print(f"✓ Chrome opened: {_DASH_URL}")
        else:
            webbrowser.open(_DASH_URL)
            print(f"✓ Default browser opened: {_DASH_URL}")
    except Exception as exc:
        print(f"⚠ Could not open browser: {exc}")
        print(f"  Manually open: {_DASH_URL}")

    print("\n" + "=" * 60)
    print(f"  Dashboard : {_DASH_URL}")
    print(f"  API Docs  : {_DASH_URL}/docs")
    print(f"  Health    : {_HEALTH_URL}")
    print("=" * 60)
    print("\nPress Ctrl+C to stop.\n")

    try:
        server_proc.wait()
    except KeyboardInterrupt:
        print("\n\nShutting down MITRA…")
        server_proc.terminate()
        server_proc.wait(timeout=5)
        print("Server stopped. Goodbye!")


if __name__ == "__main__":
    main()
