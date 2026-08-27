"""Cron job definitions shared by the scheduler, CLI, and protected HTTP hooks."""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Settings
from services.futmondo_client import FutmondoClient
from services.market_service import MarketService
from telegram_bot.bot import TelegramNotifier
from telegram_bot.client import TelegramClient

logger = logging.getLogger(__name__)


class DigestJobs:
    def __init__(self, notifier: TelegramNotifier, settings: Settings) -> None:
        self.notifier = notifier
        self.settings = settings

    def market_digest(self) -> None:
        self.settings.require_telegram()
        chat_id = int(self.settings.telegram_chat_id)
        logger.info("Starting scheduled market digest")
        self.notifier.send_budget(chat_id)
        self.notifier.send_market(
            chat_id,
            self.notifier.market.market(),
            title="Daily market digest",
        )
        logger.info("Scheduled market digest completed")

    def transfers_digest(self) -> None:
        self.settings.require_telegram()
        logger.info("Starting scheduled transfer digest")
        self.notifier.send_transfers(int(self.settings.telegram_chat_id))
        logger.info("Scheduled transfer digest completed")


def build_digest_jobs(settings: Settings) -> DigestJobs:
    settings.require("Telegram", ("telegram_bot_token",))
    client = FutmondoClient(settings)
    market = MarketService(client, wanted_min_change=settings.wanted_min_change)
    telegram = TelegramClient(
        settings.telegram_bot_token or "", timeout=settings.request_timeout
    )
    notifier = TelegramNotifier(telegram, market, settings)
    return DigestJobs(notifier, settings)


def run_scheduler(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    jobs = build_digest_jobs(settings)
    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(
        jobs.market_digest,
        CronTrigger.from_crontab(
            settings.market_digest_cron, timezone=settings.timezone
        ),
        id="market_digest",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=900,
    )
    scheduler.add_job(
        jobs.transfers_digest,
        CronTrigger.from_crontab(
            settings.transfers_digest_cron, timezone=settings.timezone
        ),
        id="transfers_digest",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=900,
    )
    logger.info(
        "Scheduler started (timezone=%s, market=%s, transfers=%s)",
        settings.timezone,
        settings.market_digest_cron,
        settings.transfers_digest_cron,
    )
    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_scheduler()
