"""Text (Responses API) and image generation with OpenAI (official SDK)."""

from __future__ import annotations

import base64

import openai
import requests

from ..i18n import L
from .base import AIError

_MAX_IMAGE_DOWNLOAD = 20 * 1024 * 1024


def _api_error(exc: Exception, model: str, what: str = "text") -> AIError:
    if isinstance(exc, openai.AuthenticationError):
        return AIError(L(
            "OpenAI rejected the API key. Check it in Settings, under AI.",
            "Το OpenAI απέρριψε το API key. Έλεγξέ το στις Ρυθμίσεις, στην ενότητα AI.",
        ))
    if isinstance(exc, openai.PermissionDeniedError):
        return AIError(L(
            f"OpenAI does not allow the model “{model}” on this account. "
            "Images may need Organization verification at OpenAI.",
            f"Το OpenAI δεν επιτρέπει το μοντέλο «{model}» σε αυτόν τον λογαριασμό. "
            "Για εικόνες μπορεί να χρειάζεται επαλήθευση οργανισμού (Organization verification) στο OpenAI.",
        ))
    if isinstance(exc, openai.NotFoundError):
        variable = "OPENAI_IMAGE_MODEL" if what == "image" else "OPENAI_TEXT_MODEL"
        return AIError(L(
            f"The model “{model}” was not found at OpenAI. Set another one in {variable}.",
            f"Το μοντέλο «{model}» δεν βρέθηκε στο OpenAI. Όρισε άλλο στο {variable}.",
        ))
    if isinstance(exc, openai.RateLimitError):
        return AIError(L(
            "OpenAI reached its request limit or the credits ran out. Try again later.",
            "Το OpenAI έφτασε το όριο αιτημάτων ή τελείωσαν τα credits. Δοκίμασε αργότερα.",
        ))
    if isinstance(exc, openai.BadRequestError):
        message = str(getattr(exc, "message", "") or exc)
        if what == "image" and any(w in message.lower() for w in ("safety", "moderation", "policy")):
            return AIError(L(
                "OpenAI rejected the image prompt for safety reasons. Try another description.",
                "Το OpenAI απέρριψε το prompt της εικόνας για λόγους ασφαλείας. Δοκίμασε άλλη περιγραφή.",
            ))
        return AIError(L(f"OpenAI rejected the request: {message}", f"Το OpenAI απέρριψε το αίτημα: {message}"))
    if isinstance(exc, openai.APIStatusError):
        return AIError(L(f"OpenAI error ({exc.status_code}). Try again later.", f"Σφάλμα OpenAI ({exc.status_code}). Δοκίμασε ξανά αργότερα."))
    if isinstance(exc, openai.APIConnectionError):
        return AIError(L("No connection to OpenAI (internet or timeout).", "Δεν υπάρχει σύνδεση με το OpenAI (internet ή timeout)."))
    return AIError(L(f"Unexpected OpenAI error: {exc.__class__.__name__}", f"Απρόσμενο σφάλμα OpenAI: {exc.__class__.__name__}"))


class OpenAIText:
    name = "openai"

    def __init__(self, api_key: str, model: str, client=None):
        self.model = model
        self._client = client or openai.OpenAI(api_key=api_key, timeout=120.0, max_retries=2)

    def complete(self, system: str, prompt: str) -> str:
        try:
            response = self._client.responses.create(model=self.model, instructions=system, input=prompt)
        except openai.OpenAIError as exc:
            raise _api_error(exc, self.model) from exc
        text = (response.output_text or "").strip()
        if not text:
            raise AIError(L("OpenAI returned an empty answer. Try again.", "Το OpenAI επέστρεψε κενή απάντηση. Δοκίμασε ξανά."))
        return text

    def verify(self) -> str:
        try:
            self._client.models.retrieve(self.model)
        except openai.OpenAIError as exc:
            raise _api_error(exc, self.model) from exc
        return f"OpenAI OK ({self.model})"


class OpenAIImages:
    def __init__(self, api_key: str, model: str, client=None, http=None):
        self.model = model
        self._client = client or openai.OpenAI(api_key=api_key, timeout=180.0, max_retries=1)
        self._http = http or requests

    def generate(self, prompt: str) -> bytes:
        kwargs: dict = {"model": self.model, "prompt": prompt, "size": "1024x1024"}
        if self.model.startswith("gpt-image"):
            kwargs["output_format"] = "jpeg"  # much smaller than PNG; stays under X's 5 MB limit
        try:
            response = self._client.images.generate(**kwargs)
        except openai.OpenAIError as exc:
            raise _api_error(exc, self.model, what="image") from exc
        item = response.data[0] if response.data else None
        if item is not None and item.b64_json:
            return base64.b64decode(item.b64_json)
        if item is not None and item.url:  # older models may return a URL instead
            try:
                resp = self._http.get(item.url, timeout=60)
            except requests.RequestException as exc:
                raise AIError(L("The image was made but could not be downloaded. Try again.", "Η εικόνα δημιουργήθηκε αλλά δεν κατέβηκε. Δοκίμασε ξανά.")) from exc
            if resp.status_code == 200 and len(resp.content) <= _MAX_IMAGE_DOWNLOAD:
                return resp.content
        raise AIError(L("OpenAI returned no image. Try again.", "Το OpenAI δεν επέστρεψε εικόνα. Δοκίμασε ξανά."))

    def verify(self) -> str:
        try:
            self._client.models.retrieve(self.model)
        except openai.OpenAIError as exc:
            raise _api_error(exc, self.model, what="image") from exc
        return L(f"Images OK ({self.model})", f"Εικόνες OK ({self.model})")
