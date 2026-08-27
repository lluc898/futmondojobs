"""Flask application factory."""

from __future__ import annotations

import logging

from flask import Flask

from api.routes import api, register_error_handlers
from config import Settings
from jobs import DigestJobs
from services.futmondo_client import FutmondoClient
from services.market_service import MarketService
from telegram_bot.bot import TelegramBot, TelegramNotifier
from telegram_bot.client import TelegramClient


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    application = Flask(__name__)
    application.config["JSON_SORT_KEYS"] = False

    futmondo = FutmondoClient(settings)
    market = MarketService(futmondo, wanted_min_change=settings.wanted_min_change)
    application.extensions["settings"] = settings
    application.extensions["futmondo"] = futmondo
    application.extensions["market"] = market

    if settings.telegram_bot_token:
        telegram = TelegramClient(
            settings.telegram_bot_token, timeout=settings.request_timeout
        )
        notifier = TelegramNotifier(telegram, market, settings)
        application.extensions["telegram"] = telegram
        application.extensions["notifier"] = notifier
        application.extensions["telegram_bot"] = TelegramBot(
            telegram, market, notifier, settings
        )
        application.extensions["digest_jobs"] = DigestJobs(notifier, settings)

    application.register_blueprint(api)
    register_error_handlers(application)
    return application


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
