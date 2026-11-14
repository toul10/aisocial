"""Command line.

    python -m aisocial init [--new-key]   create .env with a random APP_SECRET
    python -m aisocial run [--open]       start the app (and open the browser)
"""

from __future__ import annotations

import argparse
import errno
import logging
import os
import shutil
import sys
import threading
import urllib.request
import webbrowser

from .config import PROJECT_ROOT, ConfigError, Settings, is_valid_fernet_key
from .crypto import generate_key

ENV_PATH = PROJECT_ROOT / ".env"
EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
_PORT_UNAVAILABLE = {
    errno.EADDRINUSE,
    getattr(errno, "WSAEADDRINUSE", -1),
    getattr(errno, "WSAEACCES", -1),  # Windows: port reserved by the system
}


def _secret_in(lines: list[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("APP_SECRET="):
            return stripped.split("=", 1)[1].strip().strip("\"'")
    return None


def _write_private(path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def cmd_init(new_key: bool) -> int:
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        current = _secret_in(lines)
    else:
        lines = EXAMPLE_PATH.read_text(encoding="utf-8").splitlines() if EXAMPLE_PATH.exists() else []
        current = None

    if current and not new_key:
        if is_valid_fernet_key(current):
            print(".env is ready.")
            return 0
        print(
            "APP_SECRET in .env is not valid. Create a new one with:\n"
            "    python -m aisocial init --new-key\n"
            "(the saved API keys and tokens will have to be entered again)",
            file=sys.stderr,
        )
        return 1

    if current:
        shutil.copyfile(ENV_PATH, ENV_PATH.with_name(".env.bak"))
    key = generate_key()
    out, replaced = [], False
    for line in lines:
        if not replaced and line.strip().startswith("APP_SECRET="):
            out.append(f"APP_SECRET={key}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.insert(0, f"APP_SECRET={key}")
    _write_private(ENV_PATH, "\n".join(out) + "\n")
    if current:
        print(
            "Created a new APP_SECRET (the old .env was kept as .env.bak).\n"
            "Enter the saved API keys and tokens again in Settings."
        )
    else:
        print("Created .env with a new random APP_SECRET.")
    return 0


def _already_running(port: int) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/healthz", timeout=1.5) as resp:
            return resp.status == 200 and resp.read(64).startswith(b"aisocial ok")
    except (OSError, ValueError):
        return False


def _make_server(app, settings):
    from waitress import create_server

    options = {"threads": 8, "ident": "AI Social"}
    if settings.host == "127.0.0.1":
        # Browsers may resolve "localhost" to ::1 first, so listen on both loopbacks.
        # IPv6 goes first: if it is unavailable, nothing has been bound yet.
        try:
            return create_server(app, listen=f"[::1]:{settings.port} 127.0.0.1:{settings.port}", **options)
        except (OSError, ValueError) as exc:
            if isinstance(exc, OSError) and exc.errno in _PORT_UNAVAILABLE:
                raise
    return create_server(app, host=settings.host, port=settings.port, **options)


def cmd_run(open_browser: bool) -> int:
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"\n[AI Social] {exc}\n", file=sys.stderr)
        return 2

    if _already_running(settings.port):
        print(f"AI Social is already running: {settings.public_url}")
        if open_browser:
            webbrowser.open(settings.public_url)
        return 0

    from . import create_app

    app = create_app(settings, start_scheduler=False)
    try:
        server = _make_server(app, settings)
    except OSError as exc:
        if exc.errno in _PORT_UNAVAILABLE:
            print(
                f"\n[AI Social] Port {settings.port} is in use by another program.\n"
                f"Set, for example, AISOCIAL_PORT={settings.port + 1} in the .env file and start again.\n",
                file=sys.stderr,
            )
            return 3
        raise

    services = app.extensions["aisocial"]
    services.scheduler.start()
    line = "=" * 62
    print(
        f"\n{line}\n"
        f"  AI Social: {settings.public_url}\n"
        "  Leave this window open. Scheduled posts go out only\n"
        "  while the app is running.\n"
        "  To stop it, press Ctrl+C or close the window.\n"
        f"{line}\n",
        flush=True,
    )
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(settings.public_url,)).start()
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nAI Social stopped.")
    finally:
        services.scheduler.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aisocial", description="AI Social")
    sub = parser.add_subparsers(dest="command")
    init = sub.add_parser("init", help="create .env with a random APP_SECRET")
    init.add_argument("--new-key", action="store_true",
                      help="replace APP_SECRET (saved keys and tokens must be entered again)")
    run = sub.add_parser("run", help="start the app (default)")
    run.add_argument("--open", action="store_true", help="open the browser")
    args = parser.parse_args(argv)
    if args.command == "init":
        return cmd_init(args.new_key)
    return cmd_run(getattr(args, "open", False))


if __name__ == "__main__":
    sys.exit(main())
