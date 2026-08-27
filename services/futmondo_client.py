"""HTTP client for the private Futmondo endpoints used by the application."""

from __future__ import annotations

import time
from copy import deepcopy
from typing import Any

import requests

from config import ConfigurationError, Settings
from utils.token_store import TokenStore, build_token_store, token_is_valid


class FutmondoError(RuntimeError):
    """A network, authentication, or Futmondo API error."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class FutmondoClient:
    ENDPOINTS = {
        "login": "/5/login/with_mail",
        "market": "/1/market/players",
        "team_info": "/1/userteam/information",
        "bid": "/1/market/bid",
        "modify_bid": "/5/market/modifybid",
        "championship_teams": "/2/championship/teams",
        "ranking": "/1/ranking/general",
        "team_roster": "/1/userteam/roster",
        "transfers": "/1/locker/pressroom",
        "player": "/1/player/summary",
        "sell": "/1/market/putonmarket",
        "cancel_sale": "/1/market/cancelsell",
        "my_sales": "/1/market/myplayers",
        "active_championships": "/2/user/activechampionships",
    }

    def __init__(
        self,
        settings: Settings,
        *,
        session: requests.Session | None = None,
        token_store: TokenStore | None = None,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.token_store = token_store or build_token_store(settings.mongodb_uri)
        self._user_id = settings.futmondo_user_id
        self._championship_id = settings.championship_id
        self._team_id = settings.team_id
        self._active_championships: list[dict[str, Any]] | None = None
        self._scope_error: str | None = None
        self.session.headers.update(
            {
                "Origin": "https://app.futmondo.com",
                "Referer": "https://app.futmondo.com/",
                "User-Agent": "FutmondoJobs/2.0",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-GB,en;q=0.9",
                "X-Requested-With": "com.futmondo.app",
                "X-Device": "android",
            }
        )

    def login(self, *, force: bool = False) -> str:
        self.settings.require_futmondo()
        if not force:
            token, expires_at = self.token_store.get()
            if token_is_valid(token, expires_at) and self._user_id:
                self._discover_scope(str(token))
                return str(token)

        payload = {
            "header": {
                "token": None,
                "device": "android",
                "deviceId": self.settings.device_id,
                "lang": "en",
            },
            "query": {
                "mail": self.settings.futmondo_email,
                "pwd": self.settings.futmondo_password,
            },
        }
        data = self._request(self.ENDPOINTS["login"], payload)
        mobile = data.get("answer", {}).get("mobile", {})
        token = mobile.get("token")
        if not token:
            raise self._api_error(data, "Futmondo login did not return a token")
        self._user_id = mobile.get("userid") or mobile.get("userId") or self._user_id
        self._discover_scope(token)

        self.token_store.save(
            token, int(time.time()) + self.settings.token_ttl_seconds
        )
        return token

    def get_active_championships(self) -> list[dict[str, Any]]:
        self.login()
        return deepcopy(self._active_championships or [])

    def get_market(self) -> list[dict[str, Any]]:
        answer = self._authenticated_post(
            "market", {**self._scope(), "type": "market"}
        )
        return answer if isinstance(answer, list) else []

    def get_team_info(self) -> dict[str, Any]:
        answer = self._authenticated_post(
            "team_info", {**self._scope(), "type": "market"}
        )
        return answer if isinstance(answer, dict) else {}

    def get_championship_teams(self) -> list[dict[str, Any]]:
        championship_id = self._scope()["championshipId"]
        ranking_answer = self._authenticated_post(
            "ranking", {"championshipId": championship_id}
        )
        ranking = (
            ranking_answer.get("ranking", [])
            if isinstance(ranking_answer, dict)
            else []
        )
        ranking = [team for team in ranking if isinstance(team, dict)]

        try:
            details_answer = self._authenticated_post(
                "championship_teams", {"championshipId": championship_id}
            )
        except FutmondoError:
            return ranking
        details = (
            details_answer.get("teams", [])
            if isinstance(details_answer, dict)
            else []
        )
        details_by_id = {
            str(team.get("id") or team.get("_id")): team
            for team in details
            if isinstance(team, dict)
        }
        if not ranking:
            return list(details_by_id.values())
        return [
            {**team, **details_by_id.get(str(team.get("id")), {})}
            for team in ranking
        ]

    def get_team_roster(self, team_id: str | None = None) -> list[dict[str, Any]]:
        query = self._scope()
        if team_id:
            query["userteamId"] = team_id
        answer = self._authenticated_post("team_roster", query)
        return answer if isinstance(answer, list) else []

    def get_transfers(self) -> list[dict[str, Any]]:
        answer = self._authenticated_post("transfers", self._scope())
        if isinstance(answer, dict):
            news = answer.get("news", [])
            return news if isinstance(news, list) else []
        return []

    def get_player(self, player_id: str) -> dict[str, Any]:
        answer = self._authenticated_post(
            "player", {**self._scope(), "playerId": player_id}
        )
        return answer if isinstance(answer, dict) else {}

    def place_bid(
        self,
        *,
        player_id: str,
        player_slug: str,
        price: int,
        is_clause: bool = False,
        existing_bid_id: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {
            **self._scope(),
            "player_id": player_id,
            "price": int(price),
            "isClause": bool(is_clause),
        }
        endpoint = "bid"
        if existing_bid_id:
            endpoint = "modify_bid"
            query.update({"bid": existing_bid_id, "rounds": []})
        else:
            query["player_slug"] = player_slug
        answer = self._authenticated_post(endpoint, query)
        return answer if isinstance(answer, dict) else {"result": answer}

    def put_player_on_market(self, player_id: str, price: int) -> dict[str, Any]:
        answer = self._authenticated_post(
            "sell", {**self._scope(), "player_id": player_id, "price": int(price)}
        )
        return answer if isinstance(answer, dict) else {"result": answer}

    def cancel_sale(self, player_id: str) -> dict[str, Any]:
        answer = self._authenticated_post(
            "cancel_sale", {**self._scope(), "player_id": player_id}
        )
        return answer if isinstance(answer, dict) else {"result": answer}

    def get_my_sales(self) -> list[dict[str, Any]]:
        answer = self._authenticated_post(
            "my_sales", {**self._scope(), "type": "market"}
        )
        return answer if isinstance(answer, list) else []

    def _scope(self) -> dict[str, str]:
        self.login()
        if self._scope_error:
            raise ConfigurationError(self._scope_error)
        if not self._championship_id or not self._team_id:
            raise ConfigurationError(
                "No active Futmondo championship/team could be selected"
            )
        return {
            "championshipId": self._championship_id,
            "userteamId": self._team_id,
        }

    def _authenticated_post(self, endpoint_name: str, query: dict[str, Any]) -> Any:
        payload = {
            "header": self._header(self.login()),
            "query": deepcopy(query),
        }
        data = self._request(self.ENDPOINTS[endpoint_name], payload)
        answer = data.get("answer")
        if isinstance(answer, dict) and answer.get("error"):
            code = answer.get("code")
            if code and "token" in str(code).lower():
                payload["header"]["token"] = self.login(force=True)
                data = self._request(self.ENDPOINTS[endpoint_name], payload)
                answer = data.get("answer")
            if isinstance(answer, dict) and answer.get("error"):
                raise self._api_error(data, f"Futmondo rejected {endpoint_name}")
        return answer

    def _header(self, token: str) -> dict[str, str]:
        header = {"token": token}
        if self._user_id:
            header["userid"] = self._user_id
        return header

    def _discover_scope(self, token: str) -> None:
        if self._active_championships is not None:
            return
        payload = {
            "header": self._header(token),
            "query": {},
            "answer": {},
        }
        try:
            data = self._request(self.ENDPOINTS["active_championships"], payload)
        except FutmondoError:
            # Scope discovery improves stale configuration but should not block
            # installations whose explicitly configured IDs still work.
            self._active_championships = []
            return
        answer = data.get("answer")
        championships = answer.get("championships", []) if isinstance(answer, dict) else []
        self._active_championships = [
            championship
            for championship in championships
            if isinstance(championship, dict)
        ]
        selected = next(
            (
                championship
                for championship in self._active_championships
                if str(championship.get("id")) == str(self._championship_id)
            ),
            None,
        )
        if selected is None and len(self._active_championships) == 1:
            selected = self._active_championships[0]
        elif selected is None and len(self._active_championships) > 1:
            self._scope_error = (
                "Configured FUTMONDO_CHAMPIONSHIP_ID is not active and the account "
                "has multiple active championships; select one from /api/championships"
            )
            return
        if selected:
            self._championship_id = str(selected.get("id") or self._championship_id or "")
            userteam = selected.get("userteam")
            if isinstance(userteam, dict) and userteam.get("id"):
                self._team_id = str(userteam["id"])

    def _request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.post(
                f"{self.settings.futmondo_api_url}{endpoint}",
                json=payload,
                timeout=self.settings.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise FutmondoError(f"Futmondo request failed: {exc}") from exc
        except ValueError as exc:
            raise FutmondoError("Futmondo returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise FutmondoError("Futmondo returned an unexpected response")
        return data

    @staticmethod
    def _api_error(data: dict[str, Any], fallback: str) -> FutmondoError:
        answer = data.get("answer") if isinstance(data, dict) else None
        details = answer if isinstance(answer, dict) else data
        code = details.get("code") if isinstance(details, dict) else None
        message = (
            details.get("message")
            if isinstance(details, dict) and details.get("message")
            else code or fallback
        )
        return FutmondoError(str(message), code=str(code) if code else None)
