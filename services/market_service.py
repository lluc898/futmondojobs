"""Business logic and stable response models for Futmondo data."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from services.futmondo_client import FutmondoClient, FutmondoError

SORT_FIELDS = {"change", "bids", "price", "form", "average", "name"}


class MarketService:
    def __init__(self, client: FutmondoClient, *, wanted_min_change: int = 80000):
        self.client = client
        self.wanted_min_change = wanted_min_change

    def market(
        self, sort_by: str = "change", *, descending: bool = True
    ) -> list[dict[str, Any]]:
        field = sort_by if sort_by in SORT_FIELDS else "change"
        players = [self._normalize_player(player) for player in self.client.get_market()]
        return sorted(
            players,
            key=lambda player: self._sort_value(player.get(field)),
            reverse=descending,
        )

    def wanted(self) -> list[dict[str, Any]]:
        return [
            player
            for player in self.market()
            if player["change"] > self.wanted_min_change
            and str(player["owner"]).strip().lower() in {"computer", "cpu", ""}
        ]

    def budget(self) -> dict[str, int]:
        info = self.client.get_team_info()
        budget = self._integer(info.get("budget"))
        withheld = self._integer(info.get("withheld"))
        return {
            "budget": budget,
            "max_bid": self._integer(info.get("maxBid")),
            "withheld": withheld,
            "available": budget - withheld,
        }

    def teams(self) -> list[dict[str, Any]]:
        return [
            {
                "id": team.get("id") or team.get("_id"),
                "name": team.get("name", "Unknown"),
                "last_access": team.get("lastAccess"),
                "points": self._integer(team.get("points")),
                "position": self._integer(team.get("position")),
            }
            for team in self.client.get_championship_teams()
            if isinstance(team, dict)
        ]

    def championships(self) -> list[dict[str, Any]]:
        result = []
        for championship in self.client.get_active_championships():
            userteam = championship.get("userteam")
            userteam = userteam if isinstance(userteam, dict) else {}
            result.append(
                {
                    "id": championship.get("id"),
                    "name": championship.get("name", "Unknown"),
                    "status": championship.get("status"),
                    "members": self._integer(championship.get("members")),
                    "team": {
                        "id": userteam.get("id"),
                        "name": userteam.get("name", "Unknown"),
                        "budget": self._integer(userteam.get("budget")),
                        "position": self._integer(userteam.get("position")),
                    },
                }
            )
        return result

    def team_roster(self, team_id: str | None = None) -> list[dict[str, Any]]:
        return [
            self._normalize_player(player)
            for player in self.client.get_team_roster(team_id)
        ]

    def sales(self) -> list[dict[str, Any]]:
        return [self._normalize_player(player) for player in self.client.get_my_sales()]

    def sell(self, player_id: str, price: int) -> dict[str, Any]:
        if not player_id or price <= 0:
            raise ValueError("Player ID and a positive sale price are required")
        return self.client.put_player_on_market(player_id, price)

    def cancel_sale(self, player_id: str) -> dict[str, Any]:
        if not player_id:
            raise ValueError("Player ID is required")
        return self.client.cancel_sale(player_id)

    def connections(self, timezone: str) -> list[dict[str, Any]]:
        zone = ZoneInfo(timezone)
        result = []
        for team in self.teams():
            raw = team.get("last_access")
            local = "Unknown"
            sort_value = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
            if raw:
                try:
                    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                    sort_value = parsed
                    local = parsed.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    local = str(raw)
            result.append({**team, "last_access": local, "_sort": sort_value})
        result.sort(key=lambda item: item["_sort"], reverse=True)
        for item in result:
            item.pop("_sort", None)
        return result

    def transfers(
        self, *, today_only: bool = False, timezone: str = "Europe/Madrid"
    ) -> list[dict[str, Any]]:
        zone = ZoneInfo(timezone)
        today = datetime.now(zone).date()
        result: list[dict[str, Any]] = []
        for transfer in self.client.get_transfers():
            if not isinstance(transfer, dict):
                continue
            created = transfer.get("created")
            created_date = None
            if created:
                with suppress(ValueError):
                    created_date = datetime.fromisoformat(
                        str(created).replace("Z", "+00:00")
                    ).astimezone(zone)
            if today_only and (not created_date or created_date.date() != today):
                continue
            player = transfer.get("_player") or {}
            seller = transfer.get("_seller") or {}
            buyer = transfer.get("_buyer") or {}
            result.append(
                {
                    "id": transfer.get("_id"),
                    "player": player.get("name", "Unknown"),
                    "seller": seller.get("name", "Computer"),
                    "buyer": buyer.get("name", "Computer"),
                    "price": self._integer(transfer.get("price")),
                    "created": created_date.isoformat() if created_date else created,
                }
            )
        return result

    def bid(
        self, player_id: str, price: int
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if price <= 0:
            raise ValueError("Bid price must be greater than zero")
        player = self.find_market_player(player_id)
        if not player:
            raise FutmondoError("Player was not found in the current market")
        return self._place_bid(player, price)

    def bid_percentage(
        self, player_id: str, percentage: int
    ) -> tuple[dict[str, Any], dict[str, Any], int]:
        player = self.find_market_player(player_id)
        if not player:
            raise FutmondoError("Player was not found in the current market")
        base_price = player["price"] or player["value"]
        if base_price <= 0:
            raise FutmondoError("Player does not have a valid market price")
        price = int(round(base_price * (1 + percentage / 100)))
        result, normalized = self._place_bid(player, price)
        return result, normalized, price

    def find_market_player(self, player_id: str) -> dict[str, Any] | None:
        for raw in self.client.get_market():
            if str(raw.get("id") or raw.get("_id")) == str(player_id):
                player = self._normalize_player(raw)
                player["raw"] = raw
                return player
        return None

    def _place_bid(
        self, player: dict[str, Any], price: int
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raw = player.pop("raw")
        bid_data = raw.get("bid") if isinstance(raw.get("bid"), dict) else {}
        result = self.client.place_bid(
            player_id=player["id"],
            player_slug=player["slug"],
            price=price,
            existing_bid_id=bid_data.get("id"),
        )
        return result, player

    @classmethod
    def _normalize_player(cls, player: dict[str, Any]) -> dict[str, Any]:
        average_data = (
            player.get("average") if isinstance(player.get("average"), dict) else {}
        )
        fitness = average_data.get("fitness") or []
        recent = fitness[-3:] if isinstance(fitness, list) else []
        form = (
            round(sum(cls._number(value) for value in recent) / len(recent), 1)
            if recent
            else 0.0
        )
        status = player.get("status") or []
        status_text = " ".join(status) if isinstance(status, list) else str(status)
        return {
            "id": str(player.get("id") or player.get("_id") or ""),
            "slug": str(player.get("slug") or ""),
            "name": player.get("name") or "Unknown",
            "team": player.get("team") or "Unknown",
            "owner": player.get("userTeam") or player.get("owner") or "Computer",
            "value": cls._integer(player.get("value")),
            "price": cls._integer(player.get("price") or player.get("value")),
            "change": cls._integer(player.get("change")),
            "bids": cls._integer(player.get("numberOfBids")),
            "average": cls._number(average_data.get("average")),
            "form": form,
            "injured": "injured" in status_text.lower(),
            "has_bid": isinstance(player.get("bid"), dict)
            and bool(player["bid"].get("id")),
        }

    @staticmethod
    def _sort_value(value: Any) -> tuple[int, Any]:
        if isinstance(value, str):
            return (1, value.casefold())
        return (0, value if value is not None else 0)

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
