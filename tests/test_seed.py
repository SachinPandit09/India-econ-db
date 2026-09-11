import re

import pytest

from econdb.seed import parse_formula, read_catalogue, read_layout, series_rows
from econdb.series_map import IN_SCOPE, LATER_BLOCKS, build

SERIES_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+){2,}$")  # same CHECK as meta.series


@pytest.fixture(scope="module")
def layout():
    sheets, columns, linking = read_layout()
    catalogue, tickers, rbi = read_catalogue()
    cells = build(tickers, rbi)
    rows = series_rows(columns, cells, {s["sheet_code"]: s["title"] for s in sheets})
    return sheets, columns, linking, catalogue, cells, rows


def test_parse_formula_shapes():
    assert parse_formula('=IF(AND(ISNUMBER(C16),ISNUMBER(C4)),C16/C4-1,"")') == ("pct", 12, 3)
    assert parse_formula('=IF(AND(ISNUMBER(O5),ISNUMBER(O4)),(O5-O4)*100,"")') == ("bps", 1, 15)
    assert parse_formula('=IF(AND(ISNUMBER(C5),ISNUMBER(C4)),C5-C4,"")') == ("diff", 1, 3)
    for bad in ('=IF(AND(ISNUMBER(C5),ISNUMBER(D4)),C5/D4-1,"")', "=SUM(C4:C5)", ""):
        with pytest.raises(ValueError):
            parse_formula(bad)


def test_workbook_shape(layout):
    sheets, columns, linking, catalogue, _, _ = layout
    assert (len(sheets), len(catalogue), len(linking)) == (87, 206, 11)
    assert len(columns) == 1324
    assert sum(1 for c in columns if c.calc_kind) == 77


def test_every_in_scope_column_is_mapped_and_map_has_no_stale_entries(layout):
    _, columns, _, _, cells, _ = layout
    keys = {(c.sheet_code, c.block_title, c.column_label) for c in columns}
    assert set(cells) - keys == set()
    missing = []
    for c in columns:
        key = (c.sheet_code, c.block_title, c.column_label)
        later = (c.sheet_code, c.block_title) in LATER_BLOCKS
        if c.sheet_code in IN_SCOPE and not c.calc_kind and not later and key not in cells:
            missing.append(key)
    assert missing == []


def test_series_follow_the_grammar(layout):
    _, _, _, catalogue, _, rows = layout
    ids = {r["series_id"] for r in rows}
    catalogue_ids = {c["catalogue_id"] for c in catalogue}
    for r in rows:
        sid = r["series_id"]
        assert SERIES_ID.match(sid), sid
        assert sid.endswith("." + r["freq"].lower()), sid
        assert r["catalogue_id"] in catalogue_ids, sid
        assert set((r["derivation"] or {}).get("inputs", [])) <= ids, sid
    by_id = {r["series_id"]: r for r in rows}
    assert by_id["eq.in.nifty50.close.d"]["source_params"]["ticker"] == "^NSEI"
    assert by_id["cmdty.world.brent.close.d"]["source_params"]["ticker"] == "BZ=F"
    assert by_id["trade.in.exports.oil.usd.m"]["source_params"]["indicator_code"] == 42
    assert by_id["cpi.b2024.in.combined.general.index.m"]["base_year"] == "2024"
