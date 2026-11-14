"""Text generation with Claude (Anthropic Messages API, official SDK)."""

from __future__ import annotations

import re

import anthropic

from ..i18n import L
from .base import AIError

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that accept output_config.effort, and the subset that accepts server-side fallbacks.
_EFFORT_MODELS = re.compile(r"^claude-(opus|sonnet|haiku|fable|mythos)-5")
_FALLBACK_MODELS = re.compile(r"^claude-(opus-5|fable-5|mythos-5|sonnet-5-5)")


def _api_error(exc: Exception, model: str) -> AIError:
    if isinstance(exc, anthropic.AuthenticationError):
        return AIError(L(
            "Claude (Anthropic) rejected the API key. Check it in Settings, under AI.",
            "Το Claude (Anthropic) απέρριψε το API key. Έλεγξέ το στις Ρυθμίσεις, στην ενότητα AI.",
        ))
    if isinstance(exc, anthropic.PermissionDeniedError):
        return AIError(L(f"The Anthropic API key has no access: {exc.message}", f"Το Anthropic API key δεν έχει πρόσβαση: {exc.message}"))
    if isinstance(exc, anthropic.NotFoundError):
        return AIError(L(
            f"The model “{model}” was not found or is not available to your account (ANTHROPIC_MODEL).",
            f"Το μοντέλο «{model}» δεν βρέθηκε ή δεν είναι διαθέσιμο στον λογαριασμό σου (ANTHROPIC_MODEL).",
        ))
    if isinstance(exc, anthropic.RateLimitError):
        return AIError(L("Anthropic reached its request limit. Try again in a minute.", "Το Anthropic έφτασε το όριο αιτημάτων. Δοκίμασε ξανά σε ένα λεπτό."))
    if isinstance(exc, anthropic.BadRequestError):
        return AIError(L(f"Anthropic rejected the request: {exc.message}", f"Το Anthropic απέρριψε το αίτημα: {exc.message}"))
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402:
            return AIError(L("Billing problem at Anthropic: add credits to your account.", "Πρόβλημα χρέωσης στο Anthropic: πρόσθεσε credits στον λογαριασμό σου."))
        return AIError(L(f"Anthropic error ({exc.status_code}). Try again later.", f"Σφάλμα Anthropic ({exc.status_code}). Δοκίμασε ξανά αργότερα."))
    if isinstance(exc, anthropic.APIConnectionError):
        return AIError(L("No connection to Anthropic (internet or timeout).", "Δεν υπάρχει σύνδεση με το Anthropic (internet ή timeout)."))
    return AIError(L(f"Unexpected Anthropic error: {exc.__class__.__name__}", f"Απρόσμενο σφάλμα Anthropic: {exc.__class__.__name__}"))


class AnthropicText:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, effort: str = "low", client=None):
        self.model = model
        self.effort = effort
        self._client = client or anthropic.Anthropic(api_key=api_key, timeout=120.0, max_retries=2)

    def complete(self, system: str, prompt: str) -> str:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 16000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.effort and _EFFORT_MODELS.match(self.model):
            kwargs["output_config"] = {"effort": self.effort}
        try:
            if _FALLBACK_MODELS.match(self.model):
                # If a safety classifier declines, the API retries on its recommended fallback model.
                response = self._client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
            else:
                response = self._client.messages.create(**kwargs)
        except anthropic.AnthropicError as exc:
            raise _api_error(exc, self.model) from exc

        if response.stop_reason == "refusal":
            raise AIError(L(
                "Claude declined to write this text. Change the topic a little and try again.",
                "Το Claude αρνήθηκε να γράψει αυτό το κείμενο. Άλλαξε λίγο το θέμα και δοκίμασε ξανά.",
            ))
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if response.stop_reason == "max_tokens":
            raise AIError(L("Claude's answer was cut off. Try again.", "Η απάντηση του Claude κόπηκε. Δοκίμασε ξανά."))
        if not text:
            raise AIError(L("Claude returned an empty answer. Try again.", "Το Claude επέστρεψε κενή απάντηση. Δοκίμασε ξανά."))
        return text

    def verify(self) -> str:
        try:
            model = self._client.models.retrieve(self.model)
        except anthropic.AnthropicError as exc:
            raise _api_error(exc, self.model) from exc
        return f"Claude OK ({model.id})"
