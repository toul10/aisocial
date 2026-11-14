"""Runtime configuration, read from environment variables (and .env)."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from cryptography.fernet import Fernet

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 5050
TEXT_PROVIDERS = ("auto", "anthropic", "openai")


class ConfigError(RuntimeError):
    """The configuration is missing or invalid. The message is shown to the user."""


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def is_valid_fernet_key(value: str) -> bool:
    try:
        Fernet(value.encode())
    except (ValueError, TypeError):
        return False
    return True


@dataclass(frozen=True)
class Settings:
    app_secret: str
    db_path: Path
    media_dir: Path
    host: str
    port: int
    public_url: str
    password: str
    allowed_hosts: frozenset[str]
    anthropic_api_key: str
    anthropic_model: str
    anthropic_effort: str
    openai_api_key: str
    openai_text_model: str
    openai_image_model: str
    ai_text_provider: str  # "" means: use the choice saved in the app
    linkedin_api_version: str  # "" means: pick automatically
    facebook_graph_version: str
    scheduler_interval: int
    max_late_minutes: int

    @property
    def linkedin_redirect_uri(self) -> str:
        return f"{self.public_url}/oauth/linkedin/callback"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env

        def get(name: str, default: str = "") -> str:
            value = env.get(name)
            if value is None or not value.strip():
                return default
            return value.strip()

        def get_int(name: str, default: int, minimum: int = 0) -> int:
            raw = get(name)
            if not raw:
                return default
            try:
                value = int(raw)
            except ValueError as exc:
                raise ConfigError(f"Το {name} πρέπει να είναι ακέραιος αριθμός (βρέθηκε {raw!r}).") from exc
            if value < minimum:
                raise ConfigError(f"Το {name} πρέπει να είναι τουλάχιστον {minimum}.")
            return value

        def get_path(name: str, default: Path) -> Path:
            raw = get(name)
            path = Path(raw).expanduser() if raw else default
            return path if path.is_absolute() else PROJECT_ROOT / path

        secret = get("APP_SECRET")
        if not secret:
            raise ConfigError(
                "Λείπει το APP_SECRET. Ξεκίνα το πρόγραμμα με το start script "
                "(φτιάχνει μόνο του το .env) ή τρέξε: python -m aisocial init"
            )
        if not is_valid_fernet_key(secret):
            raise ConfigError(
                "Το APP_SECRET δεν είναι έγκυρο key. Φτιάξε νέο με: "
                "python -m aisocial init --new-key (τα αποθηκευμένα API keys "
                "και tokens θα πρέπει να μπουν ξανά)."
            )

        host = get("AISOCIAL_HOST", "127.0.0.1")
        port = get_int("AISOCIAL_PORT", DEFAULT_PORT, minimum=1)
        password = get("AISOCIAL_PASSWORD")
        if not is_loopback(host) and not password:
            raise ConfigError(
                f"Δεν ξεκινάω στο {host} χωρίς AISOCIAL_PASSWORD: οποιοσδήποτε στο "
                "δίκτυο θα μπορούσε να κάνει posts στους λογαριασμούς σου. Όρισε "
                "AISOCIAL_PASSWORD στο .env ή κράτα AISOCIAL_HOST=127.0.0.1."
            )

        public_url = get("AISOCIAL_PUBLIC_URL", f"http://localhost:{port}").rstrip("/")
        parsed = urlparse(public_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ConfigError("Το AISOCIAL_PUBLIC_URL πρέπει να μοιάζει με http://localhost:5050")

        allowed = {f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}", parsed.netloc.lower()}
        allowed |= {h.strip().lower() for h in get("AISOCIAL_ALLOWED_HOSTS").split(",") if h.strip()}

        provider = get("AI_TEXT_PROVIDER").lower()
        if provider and provider not in TEXT_PROVIDERS:
            raise ConfigError("Το AI_TEXT_PROVIDER πρέπει να είναι auto, anthropic ή openai.")

        effort = get("ANTHROPIC_EFFORT", "low").lower()
        if effort not in ("low", "medium", "high", "xhigh", "max"):
            raise ConfigError("Το ANTHROPIC_EFFORT πρέπει να είναι low, medium, high, xhigh ή max.")

        db_path = get_path("AISOCIAL_DB_PATH", PROJECT_ROOT / "instance" / "aisocial.db")
        media_dir = get_path("AISOCIAL_MEDIA_DIR", db_path.parent / "media")

        return cls(
            app_secret=secret,
            db_path=db_path,
            media_dir=media_dir,
            host=host,
            port=port,
            public_url=public_url,
            password=password,
            allowed_hosts=frozenset(allowed),
            anthropic_api_key=get("ANTHROPIC_API_KEY"),
            anthropic_model=get("ANTHROPIC_MODEL", "claude-opus-5-5"),
            anthropic_effort=effort,
            openai_api_key=get("OPENAI_API_KEY"),
            openai_text_model=get("OPENAI_TEXT_MODEL", "gpt-5-mini"),
            openai_image_model=get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            ai_text_provider=provider,
            linkedin_api_version=get("LINKEDIN_API_VERSION"),
            facebook_graph_version=get("FACEBOOK_GRAPH_VERSION", "v26.0"),
            scheduler_interval=get_int("AISOCIAL_SCHEDULER_INTERVAL", 15, minimum=1),
            max_late_minutes=get_int("AISOCIAL_MAX_LATE_MINUTES", 360, minimum=1),
        )
