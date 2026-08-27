from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.market_service import MarketService


class FakeFutmondo:
    def __init__(self) -> None:
        self.last_bid: dict[str, Any] | None = None

    def get_market(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "rising",
                "slug": "rising-player",
                "name": "Rising Player",
                "team": "Example FC",
                "userTeam": "Computer",
                "price": 1_000_000,
                "value": 900_000,
                "change": 100_000,
                "numberOfBids": 2,
                "average": {"average": 6.5, "fitness": [5, 6, 7, 8, 9]},
                "status": [],
                "bid": {"id": "bid-1"},
            },
            {
                "id": "falling",
                "slug": "falling-player",
                "name": "Falling Player",
                "team": "Other FC",
                "userTeam": "A manager",
                "price": 2_000_000,
                "change": -50_000,
                "numberOfBids": 0,
                "average": {"average": 4.0, "fitness": [4, 4, 5]},
                "status": ["injured"],
            },
        ]

    def get_team_info(self) -> dict[str, int]:
        return {"budget": 5_000_000, "withheld": 1_250_000, "maxBid": 4_000_000}

    def place_bid(self, **kwargs: Any) -> dict[str, str]:
        self.last_bid = kwargs
        return {"code": "api.general.ok"}

    def get_my_sales(self) -> list[dict[str, Any]]:
        return [self.get_market()[1]]

    def put_player_on_market(self, player_id: str, price: int) -> dict[str, Any]:
        return {"code": "ok", "player_id": player_id, "price": price}

    def cancel_sale(self, player_id: str) -> dict[str, Any]:
        return {"code": "ok", "player_id": player_id}

    def get_transfers(self) -> list[dict[str, Any]]:
        return [
            {
                "_id": "t1",
                "created": datetime.now(UTC).isoformat(),
                "_player": {"name": "New Player"},
                "_seller": {"name": "Computer"},
                "_buyer": {"name": "Example FC"},
                "price": 3_000_000,
            }
        ]


def test_market_normalization_sorting_and_wanted_filter() -> None:
    service = MarketService(FakeFutmondo(), wanted_min_change=80_000)

    market = service.market()
    assert [player["id"] for player in market] == ["rising", "falling"]
    assert market[0]["form"] == 8.0
    assert market[1]["injured"] is True
    assert [player["id"] for player in service.wanted()] == ["rising"]


def test_budget_bid_and_transfer_models() -> None:
    client = FakeFutmondo()
    service = MarketService(client)

    assert service.budget()["available"] == 3_750_000
    result, player, price = service.bid_percentage("rising", 10)
    assert result["code"] == "api.general.ok"
    assert player["id"] == "rising"
    assert price == 1_100_000
    assert client.last_bid == {
        "player_id": "rising",
        "player_slug": "rising-player",
        "price": 1_100_000,
        "existing_bid_id": "bid-1",
    }
    assert service.transfers(today_only=True)[0]["player"] == "New Player"
    assert service.sales()[0]["id"] == "falling"
    assert service.sell("falling", 2_100_000)["price"] == 2_100_000
    assert service.cancel_sale("falling")["code"] == "ok"
