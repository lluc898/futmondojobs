"""HTTP API, Telegram webhook, and protected cron hooks."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from config import ConfigurationError, Settings
from services.futmondo_client import FutmondoError

api = Blueprint("api", __name__)


def _extension(name: str) -> Any:
    return current_app.extensions[name]


def _provided_secret() -> str:
    bearer = request.headers.get("Authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[7:]
    return request.headers.get("X-API-Key", "")


def _protected(setting_name: str) -> Callable:
    def decorator(function: Callable) -> Callable:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            settings: Settings = _extension("settings")
            expected = getattr(settings, setting_name)
            if not expected:
                message = "This endpoint is disabled until a secret is configured"
                return jsonify({"error": message}), 503
            if not hmac.compare_digest(str(expected), _provided_secret()):
                return jsonify({"error": "Unauthorized"}), 401
            return function(*args, **kwargs)

        return wrapped

    return decorator


@api.get("/health")
def health() -> Any:
    settings: Settings = _extension("settings")
    return jsonify(
        {
            "status": "ok",
            "futmondo_configured": all(
                (
                    settings.futmondo_email,
                    settings.futmondo_password,
                    settings.championship_id,
                    settings.team_id,
                )
            ),
            "telegram_configured": bool(
                settings.telegram_bot_token and settings.telegram_chat_id
            ),
            "shared_token_cache": bool(settings.mongodb_uri),
        }
    )


@api.get("/api/players")
def players() -> Any:
    sort_by = request.args.get("sort", "change")
    descending = request.args.get("order", "desc").lower() != "asc"
    return jsonify(_extension("market").market(sort_by, descending=descending))


@api.get("/api/players/wanted")
def wanted_players() -> Any:
    return jsonify(_extension("market").wanted())


@api.get("/api/budget")
def budget() -> Any:
    return jsonify(_extension("market").budget())


@api.get("/api/transfers")
def transfers() -> Any:
    today_only = request.args.get("today", "true").lower() not in {"false", "0", "no"}
    settings: Settings = _extension("settings")
    return jsonify(
        _extension("market").transfers(
            today_only=today_only, timezone=settings.timezone
        )
    )


@api.get("/api/teams")
def teams() -> Any:
    return jsonify(_extension("market").teams())


@api.get("/api/championships")
def championships() -> Any:
    return jsonify(_extension("market").championships())


@api.get("/api/teams/<team_id>/players")
def team_players(team_id: str) -> Any:
    return jsonify(_extension("market").team_roster(team_id))


@api.get("/api/sales")
def sales() -> Any:
    return jsonify(_extension("market").sales())


@api.post("/api/sales")
@_protected("api_key")
def create_sale() -> Any:
    data = request.get_json(silent=True) or {}
    player_id = str(data.get("player_id", "")).strip()
    try:
        price = int(data.get("price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "price must be an integer"}), 400
    if not player_id or price <= 0:
        return jsonify({"error": "player_id and a positive price are required"}), 400
    return jsonify(_extension("market").sell(player_id, price))


@api.delete("/api/sales/<player_id>")
@_protected("api_key")
def cancel_sale(player_id: str) -> Any:
    return jsonify(_extension("market").cancel_sale(player_id))


@api.post("/api/bids")
@_protected("api_key")
def place_bid() -> Any:
    data = request.get_json(silent=True) or {}
    player_id = str(data.get("player_id", "")).strip()
    try:
        price = int(data.get("price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "price must be an integer"}), 400
    if not player_id or price <= 0:
        return jsonify({"error": "player_id and a positive price are required"}), 400
    result, player = _extension("market").bid(player_id, price)
    return jsonify({"result": result, "player": player, "price": price})


@api.post("/telegram/webhook")
def telegram_webhook() -> Any:
    settings: Settings = _extension("settings")
    if settings.telegram_webhook_secret:
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(settings.telegram_webhook_secret, provided):
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
    bot = current_app.extensions.get("telegram_bot")
    if bot is None:
        return jsonify({"ok": False, "error": "Telegram is not configured"}), 503
    bot.handle_update(request.get_json(silent=True) or {})
    return jsonify({"ok": True})


@api.post("/jobs/market-digest")
@_protected("cron_secret")
def market_digest() -> Any:
    _extension("digest_jobs").market_digest()
    return jsonify({"ok": True, "job": "market_digest"})


@api.post("/jobs/transfers-digest")
@_protected("cron_secret")
def transfers_digest() -> Any:
    _extension("digest_jobs").transfers_digest()
    return jsonify({"ok": True, "job": "transfers_digest"})


def register_error_handlers(app: Any) -> None:
    @app.errorhandler(ConfigurationError)
    def configuration_error(error: ConfigurationError) -> Any:
        return jsonify({"error": str(error)}), 503

    @app.errorhandler(FutmondoError)
    def futmondo_error(error: FutmondoError) -> Any:
        return jsonify({"error": str(error), "code": error.code}), 502

    @app.errorhandler(404)
    def not_found(_: Any) -> Any:
        return jsonify({"error": "Not found"}), 404
