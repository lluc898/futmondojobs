from __future__ import annotations

from typing import Any

import jobs as jobs_module
from jobs import DigestJobs


class FakeMarket:
    def market(self) -> list[dict[str, str]]:
        return [{"id": "player-1"}]


class FakeNotifier:
    def __init__(self) -> None:
        self.market = FakeMarket()
        self.budgets: list[int] = []
        self.markets: list[tuple[int, list[dict[str, str]], str]] = []
        self.transfers: list[int] = []

    def send_budget(self, chat_id: int) -> None:
        self.budgets.append(chat_id)

    def send_market(
        self, chat_id: int, players: list[dict[str, str]], *, title: str
    ) -> None:
        self.markets.append((chat_id, players, title))

    def send_transfers(self, chat_id: int) -> None:
        self.transfers.append(chat_id)


def test_market_digest_sends_budget_before_market(settings) -> None:
    notifier = FakeNotifier()

    DigestJobs(notifier, settings).market_digest()

    assert notifier.budgets == [123]
    assert notifier.markets == [
        (123, [{"id": "player-1"}], "Daily market digest")
    ]


def test_transfers_digest_targets_configured_chat(settings) -> None:
    notifier = FakeNotifier()

    DigestJobs(notifier, settings).transfers_digest()

    assert notifier.transfers == [123]


def test_scheduler_registers_single_instance_cron_jobs(settings, monkeypatch) -> None:
    notifier = FakeNotifier()
    digest_jobs = DigestJobs(notifier, settings)
    captured: dict[str, Any] = {"jobs": []}

    class FakeScheduler:
        def __init__(self, *, timezone: str) -> None:
            captured["timezone"] = timezone

        def add_job(self, function: Any, trigger: Any, **kwargs: Any) -> None:
            captured["jobs"].append((function, trigger, kwargs))

        def start(self) -> None:
            captured["started"] = True

    monkeypatch.setattr(jobs_module, "BlockingScheduler", FakeScheduler)
    monkeypatch.setattr(jobs_module, "build_digest_jobs", lambda _: digest_jobs)

    jobs_module.run_scheduler(settings)

    assert captured["timezone"] == "Europe/Madrid"
    assert captured["started"] is True
    assert [item[2]["id"] for item in captured["jobs"]] == [
        "market_digest",
        "transfers_digest",
    ]
    assert all(item[2]["max_instances"] == 1 for item in captured["jobs"])
    assert all(item[2]["coalesce"] is True for item in captured["jobs"])
