from __future__ import annotations

import hashlib
import hmac
import json
import os


def enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}


def authenticate(username: str, password: str) -> list[str] | None:
    try:
        users = json.loads(os.getenv("APP_USERS_JSON", "{}"))
        user = users.get(username)
        digest = hashlib.sha256(password.encode()).hexdigest()
        if user and hmac.compare_digest(digest, user.get("password_hash", "")):
            return user.get("roles", ["all"])
    except (json.JSONDecodeError, TypeError):
        return None
    return None
