import importlib.util
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from razzle_api.config import get_settings
from razzle_api.ingest import nflverse
from razzle_api.ingest.report import SourceStamp, SyncReport, stamp_source_syncs

API_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'sync.db'}"
    monkeypatch.setenv("RAZZLE_DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(API_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_DIR / "migrations"))
        cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")
        engine = sa.create_engine(db_url)
        yield sessionmaker(engine, expire_on_commit=False)
        engine.dispose()
    finally:
        get_settings.cache_clear()


def _load_sync_script():
    script_path = API_DIR.parents[1] / "scripts" / "sync_data.py"
    spec = importlib.util.spec_from_file_location("sync_data_k01", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_is_lazy_and_unknown_adapters_fail_closed(monkeypatch) -> None:
    sync_data = _load_sync_script()
    calls: list[str] = []

    def fake_sync(_session, _seasons):
        raise AssertionError("not called by loader")

    def fake_import(module_path: str):
        calls.append(module_path)
        return SimpleNamespace(sync=fake_sync)

    monkeypatch.setattr(sync_data.importlib, "import_module", fake_import)

    assert sync_data.ADAPTERS == {
        "nflverse": "razzle_api.ingest.nflverse",
        "crosswalk": "razzle_api.ingest.crosswalk",
    }
    assert list(sync_data.ADAPTERS) == ["nflverse", "crosswalk"]
    assert "nflverse" not in sync_data.__dict__
    with pytest.raises(ValueError, match="unknown adapter"):
        sync_data._load_adapter("not-registered")
    assert calls == []

    loaded = sync_data._load_adapter("nflverse")
    assert loaded is fake_sync
    assert calls == ["razzle_api.ingest.nflverse"]


def test_source_stamp_validation_and_sqlite_partial_upserts(session_factory) -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    later = now + timedelta(hours=1)

    with pytest.raises(ValueError, match="rows"):
        SourceStamp("bad", None, -1, now)
    with pytest.raises(ValueError, match="timezone-aware"):
        SourceStamp("bad", None, 0, datetime(2026, 7, 22, 12, 0))
    with pytest.raises(ValueError, match="UTC"):
        SourceStamp(
            "bad",
            None,
            0,
            datetime(2026, 7, 22, 12, 0, tzinfo=timezone(timedelta(hours=-4))),
        )

    with session_factory() as session:
        stamp_source_syncs(
            session,
            (
                SourceStamp("shared-source", None, 2, now),
                SourceStamp("shared-source", 2024, 3, now),
                SourceStamp("shared-source", 2025, 4, now),
            ),
        )
        stamp_source_syncs(
            session,
            (
                SourceStamp("shared-source", None, 20, later),
                SourceStamp("shared-source", 2024, 30, later),
            ),
        )
        session.commit()
        rows = (
            session.execute(
                sa.text(
                    "SELECT source, season, rows, fetched_at FROM source_syncs "
                    "ORDER BY season IS NOT NULL, season"
                )
            )
            .mappings()
            .all()
        )

    assert [dict(row) for row in rows] == [
        {
            "source": "shared-source",
            "season": None,
            "rows": 20,
            "fetched_at": later.isoformat(),
        },
        {
            "source": "shared-source",
            "season": 2024,
            "rows": 30,
            "fetched_at": later.isoformat(),
        },
        {
            "source": "shared-source",
            "season": 2025,
            "rows": 4,
            "fetched_at": now.isoformat(),
        },
    ]


def test_nflverse_sync_is_offline_and_reports_mapped_counts(
    session_factory,
    monkeypatch,
) -> None:
    players = [
        {
            "gsis_id": "00-0000001",
            "display_name": "Alpha Passer",
            "position": "QB",
            "latest_team": "BUF",
        },
        {
            "gsis_id": "00-0000002",
            "display_name": "Bravo Back",
            "position": "RB",
            "latest_team": "DET",
        },
        {
            "gsis_id": "00-0000003",
            "display_name": "Charlie Kicker",
            "position": "K",
            "latest_team": "DAL",
        },
    ]
    weeks = [
        {
            "player_id": "00-0000001",
            "position": "QB",
            "season": "2025",
            "week": "1",
            "season_type": "REG",
            "attempts": "30",
            "passing_yards": "250",
        },
        {
            "player_id": "00-0000002",
            "position": "RB",
            "season": "2025",
            "week": "1",
            "season_type": "REG",
            "carries": "15",
            "rushing_yards": "80",
        },
        {
            "player_id": "00-0000001",
            "position": "QB",
            "season": "2025",
            "week": "19",
            "season_type": "POST",
        },
        {
            "player_id": "00-0000003",
            "position": "K",
            "season": "2025",
            "week": "1",
            "season_type": "REG",
        },
    ]

    monkeypatch.setattr(nflverse, "fetch_players", lambda: players)

    def fetch_week_stats(season: int):
        assert season == 2025
        return weeks

    monkeypatch.setattr(nflverse, "fetch_week_stats", fetch_week_stats)

    with session_factory() as session:
        report = nflverse.sync(session, [2025])
        stamp_source_syncs(session, report.stamps)
        session.commit()
        player_count = session.execute(sa.text("SELECT COUNT(*) FROM players")).scalar_one()
        week_count = session.execute(sa.text("SELECT COUNT(*) FROM player_week_stats")).scalar_one()
        stamps = (
            session.execute(
                sa.text("SELECT source, season, rows FROM source_syncs ORDER BY source, season")
            )
            .mappings()
            .all()
        )

    assert report.adapter == "nflverse"
    assert report.upserted == {"players": 2, "player_week_stats:2025": 2}
    assert report.skipped == (
        "nflverse_players:1",
        "nflverse_week_stats:2025:2",
    )
    assert report.warnings == ()
    assert [(stamp.source, stamp.season, stamp.rows) for stamp in report.stamps] == [
        ("nflverse_players", None, 2),
        ("nflverse_week_stats", 2025, 2),
    ]
    assert report.stamps[0].fetched_at is report.stamps[1].fetched_at
    assert report.stamps[0].fetched_at.tzinfo is UTC
    assert player_count == 2
    assert week_count == 2
    assert [dict(row) for row in stamps] == [
        {"source": "nflverse_players", "season": None, "rows": 2},
        {"source": "nflverse_week_stats", "season": 2025, "rows": 2},
    ]


def test_report_printing_preserves_existing_lines(capsys) -> None:
    sync_data = _load_sync_script()
    report = SyncReport(
        adapter="nflverse",
        stamps=(),
        upserted={"players": 2, "player_week_stats:2025": 3},
        skipped=(),
    )

    sync_data._print_report(report)

    assert capsys.readouterr().out.splitlines() == [
        "players: upserted 2",
        "player_week_stats 2025: upserted 3",
    ]


def test_cli_maps_adapter_precondition_failure_to_exit_two(monkeypatch, capsys) -> None:
    sync_data = _load_sync_script()

    def fail_sync(_seasons: list[int]) -> None:
        raise ValueError("players table is empty; refuse to build crosswalk")

    monkeypatch.setattr(sync_data, "sync", fail_sync)

    assert sync_data.main(["--quick"]) == 2
    assert "players table is empty" in capsys.readouterr().err


def test_cli_maps_adapter_runtime_failure_to_exit_two(monkeypatch, capsys) -> None:
    sync_data = _load_sync_script()

    def fail_sync(_seasons: list[int]) -> None:
        raise RuntimeError("crosswalk lost spine gsis_id values: ['00-0001']")

    monkeypatch.setattr(sync_data, "sync", fail_sync)

    assert sync_data.main(["--quick"]) == 2
    assert "crosswalk lost spine gsis_id values" in capsys.readouterr().err
