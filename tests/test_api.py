from __future__ import annotations

from typing import Any

from app import create_app


class FakeMarket:
    def market(self, sort_by: str, *, descending: bool) -> list[dict[str, Any]]:
        return [{"id": "p1", "sort": sort_by, "descending": descending}]

    def bid(self, player_id: str, price: int):
        return {"code": "ok"}, {"id": player_id, "name": "Player"}

    def sales(self) -> list[dict[str, Any]]:
        return [{"id": "p1"}]

    def sell(self, player_id: str, price: int) -> dict[str, Any]:
        return {"id": player_id, "price": price}

    def cancel_sale(self, player_id: str) -> dict[str, Any]:
        return {"id": player_id, "cancelled": True}


class FakeBot:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def handle_update(self, update: dict[str, Any]) -> None:
        self.updates.append(update)


def test_health_read_api_and_protected_bid(settings) -> None:
    app = create_app(settings)
    app.extensions["market"] = FakeMarket()
    client = app.test_client()

    assert client.get("/health").get_json()["status"] == "ok"
    players = client.get("/api/players?sort=price&order=asc").get_json()
    assert players == [{"descending": False, "id": "p1", "sort": "price"}]
    assert client.post("/api/bids", json={"player_id": "p1", "price": 100}).status_code == 401
    response = client.post(
        "/api/bids",
        headers={"Authorization": "Bearer api-secret"},
        json={"player_id": "p1", "price": 100},
    )
    assert response.status_code == 200
    assert response.get_json()["price"] == 100

    assert client.get("/api/sales").get_json() == [{"id": "p1"}]
    sale = client.post(
        "/api/sales",
        headers={"X-API-Key": "api-secret"},
        json={"player_id": "p1", "price": 250},
    )
    assert sale.get_json()["price"] == 250
    cancelled = client.delete(
        "/api/sales/p1", headers={"X-API-Key": "api-secret"}
    )
    assert cancelled.get_json()["cancelled"] is True


def test_telegram_webhook_secret(settings) -> None:
    app = create_app(settings)
    bot = FakeBot()
    app.extensions["telegram_bot"] = bot
    client = app.test_client()

    assert client.post("/telegram/webhook", json={}).status_code == 401
    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
        json={"update_id": 1},
    )
    assert response.status_code == 200
    assert bot.updates == [{"update_id": 1}]
