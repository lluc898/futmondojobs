from __future__ import annotations

from typing import Any

import pytest
import requests

from services.futmondo_client import FutmondoClient, FutmondoError


class FailingSession:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.headers: dict[str, str] = {}

    def post(self, *args: Any, **kwargs: Any) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeResponse:
    def __init__(self, data: Any, *, http_error: bool = False) -> None:
        self.data = data
        self.http_error = http_error

    def raise_for_status(self) -> None:
        if self.http_error:
            raise requests.HTTPError("503 Service Unavailable")

    def json(self) -> Any:
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (requests.Timeout("upstream timeout"), "Futmondo request failed"),
        (FakeResponse({}, http_error=True), "Futmondo request failed"),
        (FakeResponse(ValueError("broken json")), "invalid JSON"),
        (FakeResponse(["unexpected"]), "unexpected response"),
    ],
)
def test_futmondo_external_failures_become_domain_errors(
    settings, result: Any, message: str
) -> None:
    client = FutmondoClient(settings, session=FailingSession(result))

    with pytest.raises(FutmondoError, match=message):
        client._request("/endpoint", {"query": {}})


def test_futmondo_api_error_preserves_machine_code() -> None:
    error = FutmondoClient._api_error(
        {"answer": {"error": True, "code": "market_closed", "message": "Closed"}},
        "fallback",
    )

    assert str(error) == "Closed"
    assert error.code == "market_closed"
