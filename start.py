#!/usr/bin/env python3
"""One-click start for AI Social.

Creates a private Python environment (.venv), installs the libraries, creates
.env with a random secret on the first run, then starts the app and opens the
browser. Safe to run every time: finished steps are skipped.

The start.command (macOS), start.bat (Windows) and start.sh (Linux) files run
this for you. Uses only the Python standard library.

    python3 start.py               start and open the browser
    python3 start.py --no-browser  start without opening a browser (servers)
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

MIN_PYTHON = (3, 10)
ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".requirements.sha256"


def say(message: str) -> None:
    print(f"[AI Social] {message}", flush=True)


def fail(message: str) -> None:
    print(f"\n[AI Social] ERROR: {message}\n", file=sys.stderr, flush=True)
    sys.exit(1)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv() -> Path:
    python = venv_python()
    if python.exists():
        probe = subprocess.run([str(python), "-c", "import sys"], capture_output=True)
        if probe.returncode == 0:
            return python
        say(".venv does not work (maybe Python was updated). Rebuilding it…")
        shutil.rmtree(VENV, ignore_errors=True)
    say("First start: setting up the Python environment (once, 1-3 minutes)…")
    try:
        venv.EnvBuilder(with_pip=True).create(VENV)
    except Exception as exc:  # noqa: BLE001 - show any failure in plain words
        fail(
            f"Could not create .venv ({exc}).\n"
            "On Ubuntu/Debian run: sudo apt install python3-venv  and try again."
        )
    return python


def ensure_requirements(python: Path) -> None:
    digest = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if STAMP.exists() and STAMP.read_text(encoding="utf-8").strip() == digest:
        return
    say("Installing the libraries (needs internet)…")
    pip = [str(python), "-m", "pip", "--disable-pip-version-check"]
    subprocess.run([*pip, "install", "-q", "--upgrade", "pip"], check=False)
    if subprocess.run([*pip, "install", "-q", "-r", str(REQUIREMENTS)]).returncode != 0:
        fail("Installing the libraries failed. Check your internet connection and try again.")
    STAMP.write_text(digest, encoding="utf-8")


def main() -> None:
    if sys.version_info < MIN_PYTHON:
        fail(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is needed "
            f"(found {sys.version.split()[0]}). Download it from https://www.python.org/downloads/"
        )
    os.chdir(ROOT)
    python = ensure_venv()
    ensure_requirements(python)
    if subprocess.run([str(python), "-m", "aisocial", "init"]).returncode != 0:
        fail("Could not set up the .env file (see the message above).")
    run_args = [] if "--no-browser" in sys.argv[1:] else ["--open"]
    try:
        code = subprocess.call([str(python), "-m", "aisocial", "run", *run_args])
    except KeyboardInterrupt:
        code = 0
    sys.exit(code)


if __name__ == "__main__":
    main()
