"""Shared sync-report and source-freshness contracts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SourceStamp:
    source: str
    season: int | None
    rows: int
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.rows < 0:
            raise ValueError("rows must be >= 0")
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware UTC")
        if self.fetched_at.utcoffset() != timedelta(0):
            raise ValueError("fetched_at must be UTC")


@dataclass(frozen=True)
class SyncReport:
    adapter: str
    stamps: tuple[SourceStamp, ...]
    upserted: Mapping[str, int]
    skipped: tuple[str, ...]
    warnings: tuple[str, ...] = ()


metadata = sa.MetaData()

source_syncs_table = sa.Table(
    "source_syncs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("season", sa.Integer, nullable=True),
    sa.Column("rows", sa.Integer, nullable=False),
    sa.Column("fetched_at", sa.Text, nullable=False),
)


def stamp_source_syncs(session: Session, stamps: Sequence[SourceStamp]) -> None:
    global_rows = [_stamp_payload(stamp) for stamp in stamps if stamp.season is None]
    seasonal_rows = [_stamp_payload(stamp) for stamp in stamps if stamp.season is not None]

    if global_rows:
        statement = sqlite_insert(source_syncs_table)
        statement = statement.on_conflict_do_update(
            index_elements=["source"],
            index_where=source_syncs_table.c.season.is_(None),
            set_={
                "rows": statement.excluded.rows,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
        session.execute(statement, global_rows)

    if seasonal_rows:
        statement = sqlite_insert(source_syncs_table)
        statement = statement.on_conflict_do_update(
            index_elements=["source", "season"],
            index_where=source_syncs_table.c.season.is_not(None),
            set_={
                "rows": statement.excluded.rows,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
        session.execute(statement, seasonal_rows)


def _stamp_payload(stamp: SourceStamp) -> dict[str, str | int | None]:
    return {
        "source": stamp.source,
        "season": stamp.season,
        "rows": stamp.rows,
        "fetched_at": stamp.fetched_at.astimezone(UTC).isoformat(),
    }
