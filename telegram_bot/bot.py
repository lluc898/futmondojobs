"""Telegram command handling and reusable notification formatting."""

from __future__ import annotations

import html
import logging
from collections import deque
from threading import Lock
from typing import Any

from config import Settings
from services.futmondo_client import FutmondoError
from services.market_service import SORT_FIELDS, MarketService
from telegram_bot.client import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

HELP_TEXT = """<b>Futmondo commands</b>

/market [change|bids|price|form|average] — current market
/wanted — rising players currently owned by the CPU
/budget — budget, active bids and maximum bid
/transfers — today's championship transfers
/team [name] — list a team's players
/sales — list your players currently for sale
/sell &lt;player_id&gt; &lt;price&gt; — put a player on the market
/cancel_sale &lt;player_id&gt; — remove a player from the market
/connections — championship last access times
/bid &lt;player_id&gt; &lt;amount&gt; — place or update a bid
/help — this message"""


def format_money(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def format_budget(budget: dict[str, int]) -> str:
    available = budget.get("available", 0)
    indicator = "🟢" if available >= 0 else "🔴"
    return (
        "<b>Team finances</b>\n"
        f"💰 Budget: <b>{format_money(budget.get('budget', 0))}</b>\n"
        f"🔒 Active bids: <b>{format_money(budget.get('withheld', 0))}</b>\n"
        f"{indicator} Available: <b>{format_money(available)}</b>\n"
        f"🎯 Maximum bid: <b>{format_money(budget.get('max_bid', 0))}</b>"
    )


def format_player(player: dict[str, Any]) -> str:
    change = int(player.get("change", 0))
    trend = "🔥" if change > 0 else "📉" if change < 0 else "➖"
    injury = " 🏥" if player.get("injured") else ""
    existing = " · bid active" if player.get("has_bid") else ""
    return (
        f"{trend} <b>{html.escape(str(player.get('name', 'Unknown')))}</b>{injury}\n"
        f"🏟 {html.escape(str(player.get('team', 'Unknown')))} · "
        f"{html.escape(str(player.get('owner', 'Computer')))}\n"
        f"💶 Price: <b>{format_money(player.get('price', 0))}</b>\n"
        f"📈 Change: <b>{change:+,}</b> · Bids: <b>{player.get('bids', 0)}</b>\n"
        f"⭐ Average: <b>{player.get('average', 0):g}</b> · "
        f"Form: <b>{player.get('form', 0):g}</b>{existing}"
    ).replace(",", ".")


def format_transfers(transfers: list[dict[str, Any]]) -> str:
    if not transfers:
        return "No transfers have been recorded today."
    lines = ["<b>Today's transfers</b>"]
    for transfer in transfers:
        lines.append(
            f"• <b>{html.escape(str(transfer['player']))}</b>: "
            f"{html.escape(str(transfer['seller']))} → "
            f"{html.escape(str(transfer['buyer']))} for "
            f"<b>{format_money(transfer['price'])}</b>"
        )
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(
        self,
        telegram: TelegramClient,
        market: MarketService,
        settings: Settings,
    ) -> None:
        self.telegram = telegram
        self.market = market
        self.settings = settings

    def send_budget(self, chat_id: int) -> None:
        self.telegram.send_message(chat_id, format_budget(self.market.budget()))

    def send_market(
        self,
        chat_id: int,
        players: list[dict[str, Any]],
        *,
        title: str = "Current market",
        with_buttons: bool = True,
    ) -> None:
        limited = players[: self.settings.market_player_limit]
        if not limited:
            self.telegram.send_message(chat_id, f"<b>{html.escape(title)}</b>\nNo players found.")
            return
        self.telegram.send_message(
            chat_id,
            f"<b>{html.escape(title)}</b> · showing {len(limited)} of {len(players)}",
        )
        for player in limited:
            markup = self._bid_buttons(player["id"]) if with_buttons else None
            self.telegram.send_message(
                chat_id, format_player(player), reply_markup=markup
            )

    def send_transfers(self, chat_id: int, *, today_only: bool = True) -> None:
        transfers = self.market.transfers(
            today_only=today_only, timezone=self.settings.timezone
        )
        self.telegram.send_message(
            chat_id, format_transfers(transfers[: self.settings.market_player_limit])
        )

    def send_sales(self, chat_id: int) -> None:
        self.send_market(
            chat_id,
            self.market.sales(),
            title="Players currently for sale",
            with_buttons=False,
        )

    @staticmethod
    def _bid_buttons(player_id: str) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": f"Bid +{percentage}%",
                        "callback_data": f"bid:{percentage}:{player_id}",
                    }
                    for percentage in (5, 10, 15)
                ]
            ]
        }


class TelegramBot:
    def __init__(
        self,
        telegram: TelegramClient,
        market: MarketService,
        notifier: TelegramNotifier,
        settings: Settings,
    ) -> None:
        self.telegram = telegram
        self.market = market
        self.notifier = notifier
        self.settings = settings
        self._seen_updates: set[int] = set()
        self._update_order: deque[int] = deque()
        self._update_lock = Lock()

    def handle_update(self, update: dict[str, Any]) -> None:
        if self._is_duplicate(update.get("update_id")):
            return
        callback = update.get("callback_query")
        if isinstance(callback, dict):
            self._handle_callback(callback)
            return
        message = update.get("message")
        if isinstance(message, dict) and message.get("text"):
            self._handle_message(message)

    def _handle_message(self, message: dict[str, Any]) -> None:
        chat_id = self._chat_id(message)
        if chat_id is None or not self._authorized(chat_id):
            logger.warning("Rejected Telegram message from chat %s", chat_id)
            return
        text = str(message.get("text", "")).strip()
        parts = text.split()
        command = parts[0].split("@", 1)[0].lower() if parts else ""
        args = parts[1:]
        try:
            if command in {"/start", "/help"}:
                self.telegram.send_message(chat_id, HELP_TEXT)
            elif command == "/budget":
                self.notifier.send_budget(chat_id)
            elif command == "/market":
                sort_by = args[0].lower() if args else "change"
                if sort_by not in SORT_FIELDS:
                    raise ValueError(f"Unknown sort field: {sort_by}")
                self.notifier.send_market(
                    chat_id,
                    self.market.market(sort_by),
                    title=f"Market by {sort_by}",
                )
            elif command == "/wanted":
                self.notifier.send_market(
                    chat_id, self.market.wanted(), title="Wanted players"
                )
            elif command == "/transfers":
                self.notifier.send_transfers(chat_id)
            elif command == "/sales":
                self.notifier.send_sales(chat_id)
            elif command == "/sell":
                self._sell_command(chat_id, args)
            elif command == "/cancel_sale":
                self._cancel_sale_command(chat_id, args)
            elif command == "/connections":
                self._send_connections(chat_id)
            elif command == "/team":
                self._send_team(chat_id, " ".join(args))
            elif command == "/bid":
                self._bid_command(chat_id, args)
            elif command.startswith("/"):
                self.telegram.send_message(chat_id, "Unknown command. Use /help.")
        except (FutmondoError, TelegramError, ValueError) as exc:
            logger.exception("Telegram command failed")
            self.telegram.send_message(chat_id, f"⚠️ {html.escape(str(exc))}")

    def _handle_callback(self, callback: dict[str, Any]) -> None:
        callback_id = str(callback.get("id", ""))
        message = callback.get("message") or {}
        chat_id = self._chat_id(message)
        if chat_id is None or not self._authorized(chat_id):
            if callback_id:
                self.telegram.answer_callback(callback_id, "Not authorized", alert=True)
            return
        data = str(callback.get("data", ""))
        try:
            action, percentage_text, player_id = data.split(":", 2)
            percentage = int(percentage_text)
            if action != "bid" or percentage not in {5, 10, 15} or not player_id:
                raise ValueError("Invalid bid action")
            _, player, price = self.market.bid_percentage(player_id, percentage)
            self.telegram.answer_callback(
                callback_id,
                f"Bid placed: +{percentage}% ({format_money(price)})",
            )
            self.telegram.send_message(
                chat_id,
                f"✅ <b>Bid placed</b>\n"
                f"👤 <b>{html.escape(str(player['name']))}</b>\n"
                f"📈 Increase: <b>+{percentage}%</b>\n"
                f"💶 Amount: <b>{format_money(price)}</b>",
            )
            self.notifier.send_budget(chat_id)
        except (FutmondoError, TelegramError, ValueError) as exc:
            logger.exception("Telegram bid callback failed")
            if callback_id:
                self.telegram.answer_callback(callback_id, str(exc), alert=True)

    def _bid_command(self, chat_id: int, args: list[str]) -> None:
        if len(args) != 2:
            raise ValueError("Usage: /bid <player_id> <amount>")
        try:
            price = int(args[1].replace(".", "").replace(",", ""))
        except ValueError as exc:
            raise ValueError("Bid amount must be an integer") from exc
        _, player = self.market.bid(args[0], price)
        self.telegram.send_message(
            chat_id,
            f"✅ Bid placed for <b>{html.escape(str(player['name']))}</b>: "
            f"<b>{format_money(price)}</b>",
        )
        self.notifier.send_budget(chat_id)

    def _sell_command(self, chat_id: int, args: list[str]) -> None:
        if len(args) != 2:
            raise ValueError("Usage: /sell <player_id> <price>")
        try:
            price = int(args[1].replace(".", "").replace(",", ""))
        except ValueError as exc:
            raise ValueError("Sale price must be an integer") from exc
        self.market.sell(args[0], price)
        self.telegram.send_message(
            chat_id,
            f"✅ Player <b>{html.escape(args[0])}</b> listed for "
            f"<b>{format_money(price)}</b>",
        )

    def _cancel_sale_command(self, chat_id: int, args: list[str]) -> None:
        if len(args) != 1:
            raise ValueError("Usage: /cancel_sale <player_id>")
        self.market.cancel_sale(args[0])
        self.telegram.send_message(
            chat_id, f"✅ Sale cancelled for player <b>{html.escape(args[0])}</b>"
        )

    def _send_team(self, chat_id: int, query: str) -> None:
        if not query:
            teams = self.market.teams()
            shown = teams[: self.settings.market_player_limit]
            names = ", ".join(str(team["name"]) for team in shown)
            self.telegram.send_message(
                chat_id,
                f"Usage: /team &lt;name&gt;\n"
                f"Showing {len(shown)} of {len(teams)}: {html.escape(names)}",
            )
            return
        query_lower = query.casefold()
        matches = [
            team
            for team in self.market.teams()
            if query_lower in str(team["name"]).casefold()
            or query_lower == str(team["id"]).casefold()
        ]
        if len(matches) != 1:
            raise ValueError("Team not found or name is ambiguous")
        team = matches[0]
        self.notifier.send_market(
            chat_id,
            self.market.team_roster(str(team["id"])),
            title=f"{team['name']} roster",
            with_buttons=False,
        )

    def _send_connections(self, chat_id: int) -> None:
        connections = self.market.connections(self.settings.timezone)
        shown = connections[: self.settings.market_player_limit]
        lines = [f"<b>Last connections</b> · showing {len(shown)}"] + [
            f"• <b>{html.escape(str(team['name']))}</b>: "
            f"{html.escape(str(team['last_access']))}"
            for team in shown
        ]
        self.telegram.send_message(chat_id, "\n".join(lines))

    def _authorized(self, chat_id: int) -> bool:
        return chat_id in self.settings.telegram_allowed_chat_ids

    def _is_duplicate(self, raw_update_id: Any) -> bool:
        if raw_update_id is None:
            return False
        try:
            update_id = int(raw_update_id)
        except (TypeError, ValueError):
            return False
        with self._update_lock:
            if update_id in self._seen_updates:
                return True
            if len(self._update_order) >= 2048:
                oldest = self._update_order.popleft()
                self._seen_updates.discard(oldest)
            self._update_order.append(update_id)
            self._seen_updates.add(update_id)
        return False

    @staticmethod
    def _chat_id(message: dict[str, Any]) -> int | None:
        try:
            return int(message["chat"]["id"])
        except (KeyError, TypeError, ValueError):
            return None
