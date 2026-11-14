"""Picks the AI provider from the saved keys and implements the content tasks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..i18n import L
from . import prompts
from .anthropic_provider import AnthropicText
from .base import AIError, ImageProvider, TextProvider
from .openai_provider import OpenAIImages, OpenAIText

PROVIDERS = ("anthropic", "openai")


@dataclass
class Draft:
    text: str
    count: int
    limit: int
    target: int
    over_limit: bool
    shortened: bool
    topic: str


def mask(key: str) -> str:
    return f"…{key[-4:]}" if len(key) >= 8 else ""


class AIService:
    """Keys come from the environment first, then from the encrypted app settings."""

    def __init__(self, settings, *, stored_key: Callable[[str], str], stored_provider: Callable[[], str]):
        self.settings = settings
        self._stored_key = stored_key
        self._stored_provider = stored_provider
        self._cache: dict = {}

    # --- keys & provider choice -------------------------------------------------

    def key(self, provider: str) -> tuple[str, str | None]:
        """Returns (key, source) where source is 'env', 'app' or None."""
        env_value = self.settings.anthropic_api_key if provider == "anthropic" else self.settings.openai_api_key
        if env_value:
            return env_value, "env"
        stored = self._stored_key(f"{provider}_api_key")
        return (stored, "app") if stored else ("", None)

    def preference(self) -> tuple[str, bool]:
        """Returns (auto|anthropic|openai, locked_by_env)."""
        if self.settings.ai_text_provider:
            return self.settings.ai_text_provider, True
        return (self._stored_provider() or "auto"), False

    def text_choice(self) -> str | None:
        preference, _ = self.preference()
        has_anthropic = bool(self.key("anthropic")[0])
        has_openai = bool(self.key("openai")[0])
        if preference == "anthropic":
            return "anthropic" if has_anthropic else None
        if preference == "openai":
            return "openai" if has_openai else None
        if has_anthropic:
            return "anthropic"
        return "openai" if has_openai else None

    def _make_text(self, provider: str, key: str) -> TextProvider:
        s = self.settings
        if provider == "anthropic":
            return AnthropicText(key, s.anthropic_model, s.anthropic_effort)
        return OpenAIText(key, s.openai_text_model)

    def _make_images(self, key: str) -> ImageProvider:
        return OpenAIImages(key, self.settings.openai_image_model)

    def text(self) -> TextProvider:
        choice = self.text_choice()
        if choice is None:
            preference, _ = self.preference()
            if preference in PROVIDERS:
                label = "Claude (Anthropic)" if preference == "anthropic" else "OpenAI"
                raise AIError(L(
                    f"You chose {label} for the text, but its key has not been added (Settings, under AI).",
                    f"Έχεις διαλέξει {label} για το κείμενο, αλλά δεν έχει μπει το key του (Ρυθμίσεις, ενότητα AI).",
                ))
            raise AIError(L(
                "No AI key is set. Add a Claude or OpenAI key in Settings, under AI.",
                "Δεν έχει οριστεί AI key. Πρόσθεσε ένα Claude ή OpenAI key στις Ρυθμίσεις, στην ενότητα AI.",
            ))
        key, _ = self.key(choice)
        cache_key = ("text", choice, key)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._make_text(choice, key)
        return self._cache[cache_key]

    def images(self) -> ImageProvider:
        key, _ = self.key("openai")
        if not key:
            raise AIError(L(
                "AI images need an OpenAI API key (Settings, under AI). "
                "You can always upload your own image.",
                "Για εικόνες με AI χρειάζεται OpenAI API key (Ρυθμίσεις, ενότητα AI). "
                "Μπορείς πάντα να ανεβάσεις δική σου εικόνα.",
            ))
        cache_key = ("image", key)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._make_images(key)
        return self._cache[cache_key]

    def invalidate(self) -> None:
        self._cache.clear()

    # --- status & checks -----------------------------------------------------------

    def status(self) -> dict:
        anthropic_key, anthropic_source = self.key("anthropic")
        openai_key, openai_source = self.key("openai")
        preference, locked = self.preference()
        choice = self.text_choice()
        model = None
        if choice == "anthropic":
            model = self.settings.anthropic_model
        elif choice == "openai":
            model = self.settings.openai_text_model
        return {
            "text_provider": choice,
            "text_model": model,
            "image_ready": bool(openai_key),
            "image_model": self.settings.openai_image_model,
            "preference": preference,
            "preference_locked": locked,
            "anthropic": {"set": bool(anthropic_key), "source": anthropic_source, "hint": mask(anthropic_key)},
            "openai": {"set": bool(openai_key), "source": openai_source, "hint": mask(openai_key)},
        }

    def check(self) -> dict:
        """Calls each configured provider with a cheap request (model lookup)."""
        results = {}
        for provider in PROVIDERS:
            key, _ = self.key(provider)
            if not key:
                results[provider] = {"ok": None, "message": L("No key set.", "Δεν έχει οριστεί key.")}
                continue
            try:
                messages = [self._make_text(provider, key).verify()]
                if provider == "openai":
                    messages.append(self._make_images(key).verify())
                results[provider] = {"ok": True, "message": " · ".join(messages)}
            except AIError as exc:
                results[provider] = {"ok": False, "message": str(exc)}
        return results

    # --- content tasks --------------------------------------------------------------

    def write_post(self, *, topic: str, platform, length: str, content: dict, instructions: str = "") -> Draft:
        limit = platform.max_chars
        target = min(platform.lengths.get(length) or platform.lengths.get("medium") or limit, limit)
        provider = self.text()
        system = prompts.post_system(content)
        request = prompts.post_prompt(
            topic=topic, platform=platform.key, target=target, limit=limit,
            content=content, instructions=instructions,
        )
        text = prompts.clean_output(provider.complete(system, request))
        count = platform.count(text)
        shortened = False
        if count > limit:
            retry = prompts.shorten_prompt(text=text, count=count, target=target, limit=limit)
            text = prompts.clean_output(provider.complete(system, retry))
            count = platform.count(text)
            shortened = True
        return Draft(text=text, count=count, limit=limit, target=target,
                     over_limit=count > limit, shortened=shortened, topic=topic)

    def suggest_topics(self, content: dict, count: int = 10) -> list[str]:
        raw = self.text().complete(prompts.topics_system(content), prompts.topics_prompt(content, count))
        topics = [t[:200] for t in prompts.parse_lines(raw, count)]
        if not topics:
            raise AIError(L("The AI returned no topics. Try again.", "Το AI δεν επέστρεψε θέματα. Δοκίμασε ξανά."))
        return topics

    def image_prompt(self, post_text: str) -> str:
        raw = self.text().complete(prompts.IMAGE_PROMPT_SYSTEM, prompts.image_prompt_request(post_text))
        return prompts.clean_output(raw)[:1500]

    def generate_image(self, prompt: str) -> bytes:
        prompt = prompt.strip()
        if not prompt:
            raise AIError(L("Write a description for the image.", "Γράψε μια περιγραφή για την εικόνα."))
        return self.images().generate(prompt + prompts.IMAGE_SUFFIX)
