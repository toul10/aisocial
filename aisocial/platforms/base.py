"""Shared types for social platform integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import requests


@dataclass(frozen=True)
class Field:
    """A credential the user types in when adding an account."""

    name: str
    label: str
    secret: bool = True
    placeholder: str = ""


@dataclass(frozen=True)
class Image:
    data: bytes
    mime: str
    filename: str


@dataclass(frozen=True)
class PublishResult:
    external_id: str
    url: str | None = None


class PlatformError(Exception):
    """A user-facing error from a platform.

    needs_reconnect: the credentials are invalid or expired.
    maybe_published: the request may have reached the platform (e.g. a timeout
    after sending), so the user should check before retrying.
    """

    def __init__(self, message: str, *, needs_reconnect: bool = False, maybe_published: bool = False):
        super().__init__(message)
        self.needs_reconnect = needs_reconnect
        self.maybe_published = maybe_published


def redact(text: str, values: Iterable[Any]) -> str:
    """Replace any credential value that appears in text with ***."""
    for value in values:
        if isinstance(value, str) and len(value) >= 6:
            text = text.replace(value, "***")
    return text


def error_detail(resp: requests.Response | None) -> str:
    """Best-effort human-readable message from an API error response."""
    if resp is None:
        return ""
    try:
        data = resp.json()
    except ValueError:
        text = (resp.text or "").strip()
        return text[:300] or f"HTTP {resp.status_code}"
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            desc = data.get("error_description")
            return f"{err}: {desc}" if desc else err
        for key in ("detail", "message", "title"):
            if data.get(key):
                return str(data[key])
        errors = data.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            first = errors[0]
            return str(first.get("message") or first.get("detail") or first)
    return str(data)[:300]


class Platform:
    key: str = ""
    label: str = ""
    max_chars: int = 0
    lengths: dict[str, int] = {}
    fields: tuple[Field, ...] = ()
    oauth: bool = False

    def __init__(self, http: Any = None):
        # The requests module by default (thread-safe); tests inject a fake.
        self.http = http if http is not None else requests

    def count(self, text: str) -> int:
        return len(text)

    def clean_credentials(self, creds: dict) -> dict:
        """Strip whitespace; subclasses add validation and raise PlatformError."""
        return {k: v.strip() if isinstance(v, str) else v for k, v in creds.items()}

    def missing_fields(self, creds: dict) -> list[str]:
        return [f.label for f in self.fields if not str(creds.get(f.name) or "").strip()]

    def verify(self, creds: dict) -> dict:
        """Check the credentials. Returns non-secret info such as the username."""
        raise NotImplementedError

    def publish(self, creds: dict, text: str, image: Image | None = None) -> PublishResult:
        raise NotImplementedError

    def describe(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "max_chars": self.max_chars,
            "lengths": self.lengths,
            "oauth": self.oauth,
            "fields": [
                {"name": f.name, "label": f.label, "secret": f.secret, "placeholder": f.placeholder}
                for f in self.fields
            ],
        }
