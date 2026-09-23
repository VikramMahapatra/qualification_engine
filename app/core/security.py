from __future__ import annotations

import hashlib
import secrets

_API_KEY_PREFIX = "qle"


def generate_api_key() -> str:
    return f"{_API_KEY_PREFIX}_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, hashed: str) -> bool:
    return secrets.compare_digest(hash_api_key(api_key), hashed)
