# FutmondoJobs contributor guide

Keep production code and code-facing documentation in English. The public README remains in Spanish.

## Architecture

- `app.py` builds the Flask application and wires the HTTP API, Telegram webhook, health check, and shared services.
- `api/routes.py` exposes protected JSON endpoints for market data, finances, teams, transfers, bids, and sales.
- `services/futmondo_client.py` owns authentication, active-championship discovery, token reuse, and all Futmondo HTTP calls.
- `services/market_service.py` contains domain operations and transforms raw Futmondo responses for the API and bot.
- `telegram_bot/client.py` is the synchronous Telegram Bot API client, including one bounded retry for rate limits.
- `telegram_bot/bot.py` handles commands, callbacks, authorization, duplicate updates, and formatted notifications.
- `jobs.py` runs the market and transfer digests in a dedicated APScheduler process.
- `utils/token_store.py` provides in-memory and optional MongoDB token caches with graceful fallback.

## Development rules

- Keep controllers thin and put Futmondo behavior in the service layer.
- Never include Telegram tokens, Futmondo credentials, chat IDs, or real player data in logs, tests, or documentation assets.
- Mock external HTTP services in tests; the test suite must never send Telegram messages or perform real bids.
- Preserve the configured request timeout and convert upstream failures into the project domain errors.
- Keep scheduled jobs idempotent, single-instance, and separate from Gunicorn workers.

## Verification

Run all checks before committing:

```bash
python -m ruff check .
python -m pytest
python -m compileall -q app.py config.py jobs.py services telegram_bot utils
```

GitHub Actions runs the same checks for pushes to `main` and for pull requests.
