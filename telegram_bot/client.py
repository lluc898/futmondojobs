"""Small synchronous client for the Telegram Bot HTTP API."""

from __future__ import annotations

import time
from typing import Any

import requests


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        if not token:
            raise ValueError("Telegram bot token is required")
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout
        self.session = session or requests.Session()

    def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", payload)

    def answer_callback(
        self,
        callback_query_id: str,
        text: str,
        *,
        alert: bool = False,
    ) -> dict[str, Any]:
        return self._call(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_query_id,
                "text": text[:200],
                "show_alert": alert,
            },
        )

    def set_webhook(self, url: str, secret_token: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "url": url,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": False,
        }
        if secret_token:
            payload["secret_token"] = secret_token
        return self._call("setWebhook", payload)

    def set_commands(self) -> dict[str, Any]:
        return self._call(
            "setMyCommands",
            {
                "commands": [
                    {"command": "market", "description": "Show current market"},
                    {"command": "wanted", "description": "Show rising CPU players"},
                    {"command": "budget", "description": "Show team finances"},
                    {"command": "transfers", "description": "Show today's transfers"},
                    {"command": "team", "description": "Show a team's players"},
                    {"command": "sales", "description": "Show your active sales"},
                    {"command": "sell", "description": "Put a player on the market"},
                    {"command": "cancel_sale", "description": "Cancel a player sale"},
                    {"command": "connections", "description": "Show last access times"},
                    {"command": "bid", "description": "Place a bid by player ID"},
                    {"command": "help", "description": "Show command help"},
                ]
            },
        )

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(2):
            try:
                response = self.session.post(
                    f"{self.base_url}/{method}", json=payload, timeout=self.timeout
                )
                data = response.json()
                if response.status_code == 429 and attempt == 0:
                    retry_after = data.get("parameters", {}).get("retry_after", 1)
                    time.sleep(min(max(float(retry_after), 0.1), 15.0))
                    continue
                response.raise_for_status()
            except requests.RequestException:
                # requests exceptions include the request URL, and Telegram embeds
                # the bot token in that URL. Never propagate that value to logs.
                raise TelegramError("Telegram request failed") from None
            except (TypeError, ValueError) as exc:
                raise TelegramError("Telegram returned invalid JSON") from exc
            if not data.get("ok"):
                description = data.get("description") or "Telegram rejected the request"
                raise TelegramError(description)
            return data
        raise TelegramError("Telegram rate limit retry failed")
