"""Social platforms. To add one: subclass Platform and register it in build_platforms()."""

from __future__ import annotations

from .base import Field, Image, Platform, PlatformError, PublishResult, redact
from .facebook import FacebookPlatform
from .linkedin import LinkedInPlatform
from .x import XPlatform

__all__ = [
    "Field", "Image", "Platform", "PlatformError", "PublishResult", "redact",
    "XPlatform", "LinkedInPlatform", "FacebookPlatform", "build_platforms",
]


def build_platforms(settings, http=None) -> dict[str, Platform]:
    platforms = (
        XPlatform(http=http),
        LinkedInPlatform(settings.linkedin_api_version, http=http),
        FacebookPlatform(settings.facebook_graph_version, http=http),
    )
    return {p.key: p for p in platforms}
