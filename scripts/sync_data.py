"""Sync nflverse data into the canonical SQLite database.

Run from repo root:
    uv run python scripts/sync_data.py --quick           # current + prior season
    uv run python scripts/sync_data.py --seasons 2023 2024
    uv run python scripts/sync_data.py --status          # row counts + db size, no fetch
"""

import argparse
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import cast

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from razzle_api.config import get_settings
from razzle_api.core.db import SessionLocal
from razzle_api.ingest.report import SyncReport, stamp_source_syncs

REPO_ROOT = Path(__file__).resolve().parents[1]
QUICK_SEASONS = [2024, 2025]
ADAPTERS: dict[str, str] = {
    "nflverse": "razzle_api.ingest.nflverse",
    "crosswalk": "razzle_api.ingest.crosswalk",
}
AdapterSync = Callable[[Session, list[int]], SyncReport]


def sync(seasons: list[int]) -> None:
    _migrate_to_head()
    with SessionLocal() as session:
        for adapter_name in ADAPTERS:
            report = _load_adapter(adapter_name)(session, seasons)
            stamp_source_syncs(session, report.stamps)
            _print_report(report)
        session.commit()


def _load_adapter(name: str) -> AdapterSync:
    module_path = ADAPTERS.get(name)
    if module_path is None:
        raise ValueError(f"unknown adapter: {name}")
    module = importlib.import_module(module_path)
    adapter_sync = getattr(module, "sync", None)
    if not callable(adapter_sync):
        raise TypeError(f"adapter {name} does not expose callable sync")
    return cast(AdapterSync, adapter_sync)


def _print_report(report: SyncReport) -> None:
    for key, count in report.upserted.items():
        table, separator, qualifier = key.partition(":")
        suffix = f" {qualifier}" if separator else ""
        print(f"{table}{suffix}: upserted {count}")


def status() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        for table in ("players", "player_week_stats"):
            count = session.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            print(f"{table}: {count}")
    db_path = _sqlite_path(settings.database_url)
    size_mb = db_path.stat().st_size / (1024 * 1024) if db_path and db_path.exists() else 0.0
    print(f"db size: {size_mb:.1f} MB")


def _migrate_to_head() -> None:
    cfg = Config(str(REPO_ROOT / "apps" / "api" / "alembic.ini"))
    command.upgrade(cfg, "head")


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url.removeprefix(prefix))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--quick", action="store_true", help="sync current + prior season")
    group.add_argument("--seasons", nargs="+", type=int, help="explicit seasons to sync")
    group.add_argument("--status", action="store_true", help="print row counts and db size")
    args = parser.parse_args()

    if args.status:
        status()
    else:
        sync(QUICK_SEASONS if args.quick else args.seasons)


if __name__ == "__main__":
    main()
