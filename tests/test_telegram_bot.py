from __future__ import annotations

from typing import Any

from telegram_bot.bot import TelegramBot, TelegramNotifier


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.answers: list[dict[str, Any]] = []

    def send_message(self, chat_id: int, text: str, **kwargs: Any) -> None:
        self.messages.append({"chat_id": chat_id, "text": text, **kwargs})

    def answer_callback(self, callback_id: str, text: str, **kwargs: Any) -> None:
        self.answers.append({"id": callback_id, "text": text, **kwargs})


class FakeMarket:
    def budget(self) -> dict[str, int]:
        return {"budget": 1000, "withheld": 100, "available": 900, "max_bid": 800}

    def bid_percentage(self, player_id: str, percentage: int):
        assert player_id == "player-1"
        assert percentage == 10
        return {"code": "ok"}, {"id": player_id, "name": "Test Player"}, 1100


def test_budget_command_and_bid_callback(settings) -> None:
    telegram = FakeTelegram()
    market = FakeMarket()
    notifier = TelegramNotifier(telegram, market, settings)
    bot = TelegramBot(telegram, market, notifier, settings)

    bot.handle_update({"message": {"chat": {"id": 123}, "text": "/budget"}})
    assert "Team finances" in telegram.messages[0]["text"]

    bot.handle_update(
        {
            "callback_query": {
                "id": "callback-1",
                "data": "bid:10:player-1",
                "message": {"chat": {"id": 123}},
            }
        }
    )
    assert telegram.answers[0]["id"] == "callback-1"
    assert "Bid placed" in telegram.answers[0]["text"]
    assert any("Test Player" in message["text"] for message in telegram.messages)


def test_unauthorized_chat_is_ignored(settings) -> None:
    telegram = FakeTelegram()
    market = FakeMarket()
    notifier = TelegramNotifier(telegram, market, settings)
    bot = TelegramBot(telegram, market, notifier, settings)

    bot.handle_update({"message": {"chat": {"id": 999}, "text": "/budget"}})
    assert telegram.messages == []


def test_duplicate_telegram_update_is_ignored(settings) -> None:
    telegram = FakeTelegram()
    market = FakeMarket()
    notifier = TelegramNotifier(telegram, market, settings)
    bot = TelegramBot(telegram, market, notifier, settings)
    update = {
        "update_id": 42,
        "message": {"chat": {"id": 123}, "text": "/budget"},
    }

    bot.handle_update(update)
    bot.handle_update(update)
    assert len(telegram.messages) == 1
