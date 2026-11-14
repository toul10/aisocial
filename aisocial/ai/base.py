"""Interfaces shared by the AI providers."""

from __future__ import annotations

from typing import Protocol


class AIError(Exception):
    """A user-facing AI error (missing key, refusal, network, ...)."""


class TextProvider(Protocol):
    name: str
    model: str

    def complete(self, system: str, prompt: str) -> str: ...

    def verify(self) -> str: ...


class ImageProvider(Protocol):
    model: str

    def generate(self, prompt: str) -> bytes: ...

    def verify(self) -> str: ...
