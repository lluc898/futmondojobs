from __future__ import annotations

from typing import Any

import pytest
import requests

from telegram_bot.client import TelegramClient, TelegramError


class FakeResponse:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self.data = data

    def json(self) -> dict[str, Any]:
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def post(self, url: str, *, json: dict[str, Any], timeout: float) -> FakeResponse:
        self.calls.append((url, json, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_send_message_builds_telegram_payload() -> None:
    session = FakeSession([FakeResponse(200, {"ok": True, "result": {"message_id": 7}})])
    client = TelegramClient("secret-token", timeout=3, session=session)
    keyboard = {"inline_keyboard": [[{"text": "Pujar", "callback_data": "bid"}]]}

    result = client.send_message(123, "<b>Market</b>", reply_markup=keyboard)

    assert result["result"]["message_id"] == 7
    _, payload, timeout = session.calls[0]
    assert payload == {
        "chat_id": 123,
        "text": "<b>Market</b>",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": keyboard,
    }
    assert timeout == 3


def test_rate_limit_is_retried_once(monkeypatch) -> None:
    session = FakeSession(
        [
            FakeResponse(
                429,
                {"ok": False, "parameters": {"retry_after": 2}},
            ),
            FakeResponse(200, {"ok": True, "result": True}),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr("telegram_bot.client.time.sleep", sleeps.append)

    result = TelegramClient("secret-token", session=session).answer_callback(
        "callback-1", "Done"
    )

    assert result["ok"] is True
    assert len(session.calls) == 2
    assert sleeps == [2.0]


def test_network_errors_never_expose_bot_token() -> None:
    token = "123456:very-secret-token"
    session = FakeSession([requests.ConnectionError(f"failed for bot{token}")])

    with pytest.raises(TelegramError, match="Telegram request failed") as exc_info:
        TelegramClient(token, session=session).send_message(123, "Hello")

    assert token not in str(exc_info.value)


def test_invalid_json_and_rejected_requests_are_reported() -> None:
    invalid_json = FakeSession([FakeResponse(200, ValueError("not json"))])
    rejected = FakeSession(
        [FakeResponse(200, {"ok": False, "description": "chat not found"})]
    )

    with pytest.raises(TelegramError, match="invalid JSON"):
        TelegramClient("token", session=invalid_json).send_message(123, "Hello")
    with pytest.raises(TelegramError, match="chat not found"):
        TelegramClient("token", session=rejected).send_message(123, "Hello")
