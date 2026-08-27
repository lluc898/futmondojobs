"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from dotenv import load_dotenv

load_dotenv()


class ConfigurationError(RuntimeError):
    """Raised when a feature is used without its required configuration."""


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _password_from_env() -> str | None:
    value = _first_env(
        "FUTMONDO_PASSWORD", "FUTMONDO_PWD", "FM_PWD", "PASSWORD"
    )
    if value:
        return value

    # PWD normally contains the Unix working directory. Keep it only as a
    # legacy fallback when it clearly does not contain a filesystem path.
    legacy = os.getenv("PWD")
    if legacy and not (
        legacy.startswith(("/", "\\")) or ":\\" in legacy or legacy == "/app"
    ):
        return legacy
    return None


def _as_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _as_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc


def _as_int_set(*names: str) -> frozenset[int]:
    raw = _first_env(*names)
    if not raw:
        return frozenset()
    try:
        return frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise ConfigurationError(f"{names[0]} must contain comma-separated integers") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    futmondo_email: str | None
    futmondo_password: str | None
    championship_id: str | None
    team_id: str | None
    futmondo_user_id: str | None
    telegram_bot_token: str | None
    telegram_chat_id: int | None
    telegram_allowed_chat_ids: frozenset[int]
    telegram_webhook_secret: str | None
    api_key: str | None
    cron_secret: str | None
    mongodb_uri: str | None
    device_id: str
    futmondo_api_url: str
    request_timeout: float
    token_ttl_seconds: int
    market_player_limit: int
    wanted_min_change: int
    timezone: str
    market_digest_cron: str
    transfers_digest_cron: str
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        legacy_chat_id = _first_env("USER_ID")
        chat_id_value = _first_env("TELEGRAM_CHAT_ID") or legacy_chat_id
        telegram_token = _first_env("TELEGRAM_BOT_TOKEN", "TOKEN")
        try:
            chat_id = int(chat_id_value) if chat_id_value else None
        except ValueError as exc:
            raise ConfigurationError("TELEGRAM_CHAT_ID must be an integer") from exc

        allowed = _as_int_set("TELEGRAM_ALLOWED_CHAT_IDS")
        if not allowed and chat_id is not None:
            allowed = frozenset({chat_id})

        return cls(
            futmondo_email=_first_env("FUTMONDO_EMAIL", "MAIL"),
            futmondo_password=_password_from_env(),
            championship_id=_first_env("FUTMONDO_CHAMPIONSHIP_ID", "CHAMPIONSHIP_ID"),
            team_id=_first_env("FUTMONDO_TEAM_ID", "USERTEAM_ID", "USER_TEAM_ID"),
            futmondo_user_id=_first_env("FUTMONDO_USER_ID"),
            telegram_bot_token=telegram_token,
            telegram_chat_id=chat_id,
            telegram_allowed_chat_ids=allowed,
            telegram_webhook_secret=_first_env("TELEGRAM_WEBHOOK_SECRET")
            or (sha256(telegram_token.encode()).hexdigest() if telegram_token else None),
            api_key=_first_env("API_KEY"),
            cron_secret=_first_env("CRON_SECRET"),
            mongodb_uri=_first_env("MONGODB_URI"),
            device_id=_first_env("FUTMONDO_DEVICE_ID", "DEVICE_ID") or "futmondojobs",
            futmondo_api_url=(
                _first_env("FUTMONDO_API_URL") or "https://api.futmondo.com"
            ).rstrip("/"),
            request_timeout=_as_float("REQUEST_TIMEOUT_SECONDS", 20.0),
            token_ttl_seconds=_as_int("TOKEN_TTL_SECONDS", 3300),
            market_player_limit=max(1, _as_int("MARKET_PLAYER_LIMIT", 20)),
            wanted_min_change=_as_int("WANTED_MIN_CHANGE", 80000),
            timezone=_first_env("TZ", "APP_TIMEZONE") or "Europe/Madrid",
            market_digest_cron=_first_env("MARKET_DIGEST_CRON") or "0 7 * * *",
            transfers_digest_cron=_first_env("TRANSFERS_DIGEST_CRON") or "45 7 * * *",
            log_level=(_first_env("LOG_LEVEL") or "INFO").upper(),
        )

    def require(self, feature: str, fields: Iterable[str]) -> None:
        missing = [field for field in fields if not getattr(self, field)]
        if missing:
            env_names = ", ".join(field.upper() for field in missing)
            raise ConfigurationError(f"{feature} is not configured; missing: {env_names}")

    def require_futmondo(self) -> None:
        self.require(
            "Futmondo",
            ("futmondo_email", "futmondo_password"),
        )

    def require_telegram(self) -> None:
        self.require("Telegram", ("telegram_bot_token", "telegram_chat_id"))
