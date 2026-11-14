"""Encryption at rest for API keys and tokens (Fernet, keyed by APP_SECRET)."""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken

from .i18n import L


class DecryptionError(RuntimeError):
    """Stored data cannot be decrypted, usually because APP_SECRET changed."""


def generate_key() -> str:
    return Fernet.generate_key().decode()


class SecretBox:
    def __init__(self, key: str):
        self._fernet = Fernet(key.encode())

    def encrypt_text(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode())

    def decrypt_text(self, token: bytes) -> str:
        try:
            return self._fernet.decrypt(bytes(token)).decode()
        except InvalidToken as exc:
            raise DecryptionError(L(
                "The saved details cannot be read: APP_SECRET in .env has probably changed. "
                "Enter the keys/tokens again in Settings.",
                "Τα αποθηκευμένα στοιχεία δεν διαβάζονται: μάλλον άλλαξε το APP_SECRET στο .env. "
                "Βάλε ξανά τα keys/tokens στις Ρυθμίσεις.",
            )) from exc

    def encrypt_json(self, data: dict) -> bytes:
        return self.encrypt_text(json.dumps(data, separators=(",", ":")))

    def decrypt_json(self, token: bytes) -> dict:
        return json.loads(self.decrypt_text(token))
