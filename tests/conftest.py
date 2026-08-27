from __future__ import annotations

import pytest

from config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        futmondo_email="manager@example.com",
        futmondo_password="password",
        championship_id="championship-1",
        team_id="team-1",
        futmondo_user_id="user-1",
        telegram_bot_token="telegram-token",
        telegram_chat_id=123,
        telegram_allowed_chat_ids=frozenset({123}),
        telegram_webhook_secret="webhook-secret",
        api_key="api-secret",
        cron_secret="cron-secret",
        mongodb_uri=None,
        device_id="test-device",
        futmondo_api_url="https://futmondo.test",
        request_timeout=1.0,
        token_ttl_seconds=3300,
        market_player_limit=5,
        wanted_min_change=80000,
        timezone="Europe/Madrid",
        market_digest_cron="0 7 * * *",
        transfers_digest_cron="45 7 * * *",
        log_level="WARNING",
    )
