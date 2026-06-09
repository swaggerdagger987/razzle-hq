"""nflverse adapter: fetch release CSVs, map to the canonical schema, upsert into SQLite.

Three layers, kept separate so each is testable on its own:
- fetch_*: network only, no DB.
- map_*: pure row transforms, no I/O.
- upsert_*: DB only, no network.
"""

import csv
import gzip
import io
import urllib.request

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

PLAYERS_URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
WEEK_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/"
    "stats_player_week_{season}.csv"
)
USER_AGENT = "razzle-sync/1.0"
TIMEOUT_SECONDS = 120

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE"}

# Mirrors STAT_COLUMNS in migration 0001 (and the matching subset of
# razzle_api.domain.scoring.engine.PlayerWeekStats). Defined once here so the
# adapter never imports the migration.
STAT_COLUMNS = [
    "pass_att",
    "pass_cmp",
    "pass_yd",
    "pass_td",
    "pass_int",
    "pass_sack",
    "pass_two_pt",
    "rush_att",
    "rush_yd",
    "rush_td",
    "rush_two_pt",
    "target",
    "rec",
    "rec_yd",
    "rec_td",
    "rec_two_pt",
    "fumble",
    "fumble_lost",
    "return_yd",
    "return_td",
    "special_teams_td",
    "pat_made",
    "pat_missed",
    "fg_made",
    "fg_missed",
]

# nflverse weekly column -> our column. Tuples list accepted source names in
# priority order: the 2025+ format first, then the pre-2025 name.
_DIRECT_STAT_MAP: dict[str, tuple[str, ...]] = {
    "pass_att": ("attempts",),
    "pass_cmp": ("completions",),
    "pass_yd": ("passing_yards",),
    "pass_td": ("passing_tds",),
    "pass_int": ("passing_interceptions", "interceptions"),
    "pass_sack": ("sacks_suffered", "sacks"),
    "pass_two_pt": ("passing_2pt_conversions",),
    "rush_att": ("carries",),
    "rush_yd": ("rushing_yards",),
    "rush_td": ("rushing_tds",),
    "rush_two_pt": ("rushing_2pt_conversions",),
    "target": ("targets",),
    "rec": ("receptions",),
    "rec_yd": ("receiving_yards",),
    "rec_td": ("receiving_tds",),
    "rec_two_pt": ("receiving_2pt_conversions",),
    "special_teams_td": ("special_teams_tds",),
}

_FUMBLE_SOURCES = ("rushing_fumbles", "receiving_fumbles", "sack_fumbles")
_FUMBLE_LOST_SOURCES = ("rushing_fumbles_lost", "receiving_fumbles_lost", "sack_fumbles_lost")

metadata = sa.MetaData()

players_table = sa.Table(
    "players",
    metadata,
    sa.Column("gsis_id", sa.String, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("position", sa.String, nullable=False),
    sa.Column("team", sa.String, nullable=True),
    sa.Column("sleeper_id", sa.String, nullable=True),
)

player_week_stats_table = sa.Table(
    "player_week_stats",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("player_id", sa.String, nullable=False),
    sa.Column("season", sa.Integer, nullable=False),
    sa.Column("week", sa.Integer, nullable=False),
    *[sa.Column(name, sa.Float, nullable=False) for name in STAT_COLUMNS],
)


def fetch_players() -> list[dict]:
    return _fetch_csv_rows(PLAYERS_URL)


def fetch_week_stats(season: int) -> list[dict]:
    return _fetch_csv_rows(WEEK_STATS_URL.format(season=season))


def _fetch_csv_rows(url: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = response.read()
    if url.endswith(".gz"):
        payload = gzip.decompress(payload)
    # players.csv ships with a BOM; utf-8-sig handles both cases.
    text = payload.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def map_player_row(row: dict) -> dict | None:
    gsis_id = (row.get("gsis_id") or "").strip()
    position = (row.get("position") or "").strip()
    if not gsis_id or position not in FANTASY_POSITIONS:
        return None
    return {
        "gsis_id": gsis_id,
        "name": (row.get("display_name") or "").strip(),
        "position": position,
        "team": (row.get("latest_team") or "").strip() or None,
    }


def map_week_row(row: dict) -> dict | None:
    player_id = (row.get("player_id") or "").strip()
    position = (row.get("position") or "").strip()
    if not player_id or position not in FANTASY_POSITIONS:
        return None
    if (row.get("season_type") or "").strip() != "REG":
        return None
    mapped = {
        "player_id": player_id,
        "week": int(_to_float(row.get("week"))),
        **{column: 0.0 for column in STAT_COLUMNS},
    }
    for column, sources in _DIRECT_STAT_MAP.items():
        mapped[column] = _first_present(row, sources)
    mapped["fumble"] = sum(_to_float(row.get(source)) for source in _FUMBLE_SOURCES)
    mapped["fumble_lost"] = sum(_to_float(row.get(source)) for source in _FUMBLE_LOST_SOURCES)
    return mapped


def _first_present(row: dict, sources: tuple[str, ...]) -> float:
    for source in sources:
        if source in row:
            return _to_float(row[source])
    return 0.0


def _to_float(value: object) -> float:
    if value is None or value in ("", "NA", "NaN"):
        return 0.0
    return float(value)


def upsert_players(session: Session, rows: list[dict]) -> int:
    for chunk in _chunks(rows):
        statement = sqlite_insert(players_table)
        statement = statement.on_conflict_do_update(
            index_elements=["gsis_id"],
            set_={
                "name": statement.excluded.name,
                "position": statement.excluded.position,
                "team": statement.excluded.team,
            },
        )
        session.execute(statement, chunk)
    return len(rows)


def upsert_week_stats(session: Session, season: int, rows: list[dict]) -> int:
    zeroes = {column: 0.0 for column in STAT_COLUMNS}
    payload = [{**zeroes, **row, "season": season} for row in rows]
    for chunk in _chunks(payload):
        statement = sqlite_insert(player_week_stats_table)
        statement = statement.on_conflict_do_update(
            index_elements=["player_id", "season", "week"],
            set_={column: statement.excluded[column] for column in STAT_COLUMNS},
        )
        session.execute(statement, chunk)
    return len(payload)


def _chunks(rows: list[dict], size: int = 500) -> list[list[dict]]:
    return [rows[start : start + size] for start in range(0, len(rows), size)]
