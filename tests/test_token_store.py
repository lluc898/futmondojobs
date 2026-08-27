from __future__ import annotations

from utils.token_store import (
    MemoryTokenStore,
    ResilientTokenStore,
    build_token_store,
    token_is_valid,
)


class BrokenTokenStore:
    def get(self) -> tuple[str | None, int | None]:
        raise OSError("cache unavailable")

    def save(self, token: str, expires_at: int) -> None:
        raise OSError("cache unavailable")


def test_memory_token_store_round_trip() -> None:
    store = MemoryTokenStore()

    assert store.get() == (None, None)
    store.save("token", 1234)

    assert store.get() == ("token", 1234)


def test_resilient_store_falls_back_to_memory_when_primary_fails() -> None:
    store = ResilientTokenStore(BrokenTokenStore())

    store.save("fallback-token", 4567)

    assert store.get() == ("fallback-token", 4567)


def test_token_validity_keeps_a_thirty_second_safety_window(monkeypatch) -> None:
    monkeypatch.setattr("utils.token_store.time.time", lambda: 1_000)

    assert token_is_valid("token", 1_031) is True
    assert token_is_valid("token", 1_030) is False
    assert token_is_valid(None, 2_000) is False


def test_build_token_store_without_mongodb_uses_memory() -> None:
    assert isinstance(build_token_store(None), MemoryTokenStore)
