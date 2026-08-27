from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.futmondo_client import FutmondoClient
from utils.token_store import MemoryTokenStore


class FakeResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.data


class FakeSession:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        return FakeResponse(self.responses.pop(0))


def test_login_is_cached_and_payloads_are_scoped(settings) -> None:
    session = FakeSession(
        [
            {"answer": {"mobile": {"token": "session-token"}}},
            {
                "answer": {
                    "championships": [
                        {"id": "championship-1", "userteam": {"id": "team-1"}}
                    ]
                }
            },
            {"answer": [{"id": "p1"}]},
            {"answer": [{"id": "p2"}]},
        ]
    )
    client = FutmondoClient(
        settings, session=session, token_store=MemoryTokenStore()
    )

    assert client.get_market() == [{"id": "p1"}]
    assert client.get_market() == [{"id": "p2"}]
    assert len(session.calls) == 4
    assert session.calls[0][0].endswith("/5/login/with_mail")
    assert session.calls[1][0].endswith("/2/user/activechampionships")
    market_payload = session.calls[2][1]["json"]
    assert market_payload["header"] == {
        "token": "session-token",
        "userid": "user-1",
    }
    assert market_payload["query"]["championshipId"] == "championship-1"
    assert market_payload["query"]["userteamId"] == "team-1"


def test_login_discovers_futmondo_user_id(settings) -> None:
    settings = replace(settings, futmondo_user_id=None)
    session = FakeSession(
        [
            {
                "answer": {
                    "mobile": {"token": "session-token", "userid": "discovered-user"}
                }
            },
            {
                "answer": {
                    "championships": [
                        {
                            "id": "discovered-championship",
                            "userteam": {"id": "discovered-team"},
                        }
                    ]
                }
            },
            {"answer": []},
        ]
    )
    client = FutmondoClient(
        settings, session=session, token_store=MemoryTokenStore()
    )

    client.get_market()
    market_payload = session.calls[2][1]["json"]
    assert market_payload["header"]["userid"] == "discovered-user"
    assert market_payload["query"]["championshipId"] == "discovered-championship"
    assert market_payload["query"]["userteamId"] == "discovered-team"


def test_championship_teams_are_limited_to_current_ranking(settings) -> None:
    session = FakeSession(
        [
            {"answer": {"mobile": {"token": "token"}}},
            {
                "answer": {
                    "championships": [
                        {"id": "championship-1", "userteam": {"id": "team-1"}}
                    ]
                }
            },
            {
                "answer": {
                    "ranking": [
                        {"id": "team-1", "name": "One", "position": 1},
                        {"id": "team-2", "name": "Two", "position": 2},
                    ]
                }
            },
            {
                "answer": {
                    "teams": [
                        {"id": "team-1", "name": "One", "lastAccess": "now"},
                        {"id": "team-2", "name": "Two", "lastAccess": "later"},
                        {"id": "other-group", "name": "Other"},
                    ]
                }
            },
        ]
    )
    client = FutmondoClient(
        settings, session=session, token_store=MemoryTokenStore()
    )

    teams = client.get_championship_teams()
    assert [team["id"] for team in teams] == ["team-1", "team-2"]
    assert teams[0]["lastAccess"] == "now"
