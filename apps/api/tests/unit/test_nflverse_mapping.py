from razzle_api.ingest.nflverse import STAT_COLUMNS, map_week_row

NEW_FORMAT_ROW = {
    "player_id": "00-0034796",
    "position": "QB",
    "season": "2024",
    "week": "3",
    "season_type": "REG",
    "completions": "22",
    "attempts": "30",
    "passing_yards": "275",
    "passing_tds": "2",
    "passing_interceptions": "1",
    "sacks_suffered": "3",
    "passing_2pt_conversions": "0",
    "carries": "8",
    "rushing_yards": "45",
    "rushing_tds": "1",
    "rushing_2pt_conversions": "0",
    "targets": "0",
    "receptions": "0",
    "receiving_yards": "0",
    "receiving_tds": "0",
    "receiving_2pt_conversions": "0",
    "rushing_fumbles": "1",
    "receiving_fumbles": "0",
    "sack_fumbles": "1",
    "rushing_fumbles_lost": "1",
    "receiving_fumbles_lost": "0",
    "sack_fumbles_lost": "0",
    "special_teams_tds": "0",
}

OLD_FORMAT_ROW = {
    **{
        key: value
        for key, value in NEW_FORMAT_ROW.items()
        if key not in ("passing_interceptions", "sacks_suffered")
    },
    "interceptions": "1",
    "sacks": "3",
}


def test_new_and_old_format_rows_map_identically() -> None:
    mapped_new = map_week_row(NEW_FORMAT_ROW)
    mapped_old = map_week_row(OLD_FORMAT_ROW)

    assert mapped_new is not None
    assert mapped_new == mapped_old
    assert mapped_new["player_id"] == "00-0034796"
    assert mapped_new["week"] == 3
    assert mapped_new["pass_yd"] == 275.0
    assert mapped_new["pass_int"] == 1.0
    assert mapped_new["pass_sack"] == 3.0
    assert mapped_new["fumble"] == 2.0
    assert mapped_new["fumble_lost"] == 1.0
    assert set(STAT_COLUMNS) <= set(mapped_new)


def test_na_values_coerce_to_zero() -> None:
    row = {**NEW_FORMAT_ROW, "passing_yards": "NA", "rushing_yards": "", "targets": "NaN"}

    mapped = map_week_row(row)

    assert mapped is not None
    assert mapped["pass_yd"] == 0.0
    assert mapped["rush_yd"] == 0.0
    assert mapped["target"] == 0.0


def test_non_regular_season_row_is_filtered() -> None:
    assert map_week_row({**NEW_FORMAT_ROW, "season_type": "POST"}) is None


def test_non_fantasy_position_row_is_filtered() -> None:
    assert map_week_row({**NEW_FORMAT_ROW, "position": "K"}) is None
