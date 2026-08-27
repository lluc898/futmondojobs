"""Administrative CLI for jobs, the scheduler, and Telegram webhook setup."""

from __future__ import annotations

import argparse
import logging

from config import ConfigurationError, Settings
from jobs import build_digest_jobs, run_scheduler
from telegram_bot.client import TelegramClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage FutmondoJobs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scheduler", help="Run the blocking cron scheduler")
    subparsers.add_parser("market-digest", help="Send the market digest now")
    subparsers.add_parser("transfers-digest", help="Send today's transfers now")
    webhook = subparsers.add_parser("set-webhook", help="Configure the Telegram webhook")
    webhook.add_argument("url", help="Public HTTPS base URL or full webhook URL")
    args = parser.parse_args()

    settings = Settings.from_env()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    if args.command == "scheduler":
        run_scheduler(settings)
        return
    if args.command == "market-digest":
        build_digest_jobs(settings).market_digest()
        return
    if args.command == "transfers-digest":
        build_digest_jobs(settings).transfers_digest()
        return
    if args.command == "set-webhook":
        settings.require("Telegram", ("telegram_bot_token",))
        url = args.url.rstrip("/")
        if not url.endswith("/telegram/webhook"):
            url += "/telegram/webhook"
        client = TelegramClient(
            settings.telegram_bot_token or "", timeout=settings.request_timeout
        )
        client.set_webhook(url, settings.telegram_webhook_secret)
        client.set_commands()
        print(f"Telegram webhook configured: {url}")


if __name__ == "__main__":
    try:
        main()
    except ConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
