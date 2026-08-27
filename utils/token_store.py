"""Optional shared token caching with an in-memory fallback."""

from __future__ import annotations

import logging
import time
from typing import Protocol

logger = logging.getLogger(__name__)


class TokenStore(Protocol):
    def get(self) -> tuple[str | None, int | None]: ...

    def save(self, token: str, expires_at: int) -> None: ...


class MemoryTokenStore:
    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: int | None = None

    def get(self) -> tuple[str | None, int | None]:
        return self._token, self._expires_at

    def save(self, token: str, expires_at: int) -> None:
        self._token = token
        self._expires_at = expires_at


class MongoTokenStore:
    def __init__(self, uri: str) -> None:
        from pymongo import MongoClient

        self._collection = MongoClient(
            uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000
        ).get_database().tokens

    def get(self) -> tuple[str | None, int | None]:
        document = self._collection.find_one({"_id": "login_token"})
        if not document:
            return None, None
        return document.get("token"), document.get("expires_at")

    def save(self, token: str, expires_at: int) -> None:
        self._collection.update_one(
            {"_id": "login_token"},
            {"$set": {"token": token, "expires_at": expires_at}},
            upsert=True,
        )


class ResilientTokenStore:
    """Use memory whenever the configured shared cache is unavailable."""

    def __init__(self, primary: TokenStore | None = None) -> None:
        self._primary = primary
        self._memory = MemoryTokenStore()

    def get(self) -> tuple[str | None, int | None]:
        if self._primary:
            try:
                token, expires_at = self._primary.get()
                if token:
                    return token, expires_at
            except Exception:
                logger.warning("Shared token cache is unavailable; using memory", exc_info=True)
        return self._memory.get()

    def save(self, token: str, expires_at: int) -> None:
        self._memory.save(token, expires_at)
        if self._primary:
            try:
                self._primary.save(token, expires_at)
            except Exception:
                logger.warning("Could not save token to shared cache", exc_info=True)


def build_token_store(mongodb_uri: str | None) -> TokenStore:
    if not mongodb_uri:
        return MemoryTokenStore()
    try:
        return ResilientTokenStore(MongoTokenStore(mongodb_uri))
    except Exception:
        logger.warning("Could not initialize MongoDB token cache; using memory")
        return MemoryTokenStore()


def token_is_valid(token: str | None, expires_at: int | None) -> bool:
    return bool(token and expires_at and expires_at > int(time.time()) + 30)
