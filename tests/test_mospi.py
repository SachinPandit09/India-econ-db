import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from econdb.sources import mospi

FIXTURES = Path(__file__).parent / "fixtures" / "mospi"
SERIES_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+){2,}$")  # same CHECK as meta.series
NAMED = {
    "cpi2024_current": ("CPI2024", {"base_year": "2024", "series": "Current"}),
    "cpi2024_back": ("CPI2024BACK", {"base_year": "2024", "series": "Back"}),
    "cpi2012_group": ("CPI2012", {"base_year": "2012"}),
    "cpi2012_item": ("CPI2012ITEM", {"base_year": "2012"}),
    "cpi2010_group": ("CPI2010", {"base_year": "2010"}),
    "iip_monthly_2022-23": ("IIP", {"base_year": "2022-23", "frequency": "Monthly"}),
    "iip_annual_2011-12": ("IIP", {"base_year": "2011-12", "frequency": "Annually"}),
    "cpialrl_ind1": ("CPIALRL", {"indicator_code": 1}),
    "cpialrl_ind2": ("CPIALRL", {"indicator_code": 2}),
    "asi_2008_2digit_in": ("ASI", {"classification_year": 2008}),
    "asi_2004_all_in": ("ASI", {"classification_year": 2004}),
    "energy_ind1_use1": ("ENERGY", {"indicator_code": 1}),
    "energy_ind1_use2": ("ENERGY", {"indicator_code": 1}),
    "mnre_type1": ("MNRE", {}),
    "mnre_type5": ("MNRE", {}),
    "isp_freq1": ("ISP", {}),
    "isp_freq2": ("ISP", {}),
    "hces_ind1": ("HCES", {"indicator_code": 1}),
    "hces_ind3": ("HCES", {"indicator_code": 3}),
    "nfhs_ind1": ("NFHS", {"indicator_code": 1}),
}


def chunk_for(name: str) -> mospi.Chunk:
    if name in NAMED:
        dataset, params = NAMED[name]
    elif m := re.fullmatch(r"rbi_(\d+)", name):
        dataset, params = "RBI", {"sub_indicator_code": int(m[1])}
    elif m := re.fullmatch(r"wpi_(.+)", name):
        dataset, params = "WPI", {"base_year": m[1]}
    elif m := re.fullmatch(r"nas_c(\d+)_([aq])_(.+)", name):
        params = {
            "indicator_code": int(m[1]),
            "frequency_code": 1 if m[2] == "a" else 2,
            "base_year": m[3],
        }
        dataset = "NAS"
    elif m := re.fullmatch(r"plfs_a_ind(\d)_yt(\d)", name):
        dataset, params = (
            "PLFS",
            {"indicator_code": int(m[1]), "frequency_code": 1, "year_type_code": int(m[2])},
        )
    elif m := re.fullmatch(r"plfs_m_ind(\d)", name):
        dataset, params = "PLFS", {"indicator_code": int(m[1]), "frequency_code": 3}
    else:
        raise KeyError(name)
    return mospi.Chunk(dataset, name, "/fixture", tuple(sorted(params.items())))


def batch_for(name: str) -> mospi.Batch:
    rows, meta = mospi.parse((FIXTURES / f"{name}.json").read_bytes(), name)
    return mospi.normalise(chunk_for(name), [(f"fixture/{name}", rows, meta)])


DATA_FIXTURES = sorted(p.stem for p in FIXTURES.glob("*.json") if not p.stem.startswith("meta_"))


@pytest.mark.parametrize("name", DATA_FIXTURES)
def test_every_fixture_normalises_to_valid_rows(name):
    b = batch_for(name)
    assert b.rows_in == 10
    for sid, start, end, freq, value, _stage, _ref in b.obs:
        assert SERIES_ID.match(sid), sid
        assert sid.endswith("." + freq.lower()) and start <= end
        assert isinstance(value, Decimal)
    ambiguous = {
        "wpi_1993-94": 1
    }  # the source repeats 'FUEL POWER LIGHT & LUBRICANTS' with 4 values
    for target, rows in (("obs", b.obs), ("cpi", b.cpi), ("detail", b.detail)):
        kept, conflicts = mospi.dedupe(rows, target)
        assert len(conflicts) == (ambiguous.get(name, 0) if target == "obs" else 0)
        assert not {k for k in map(mospi.KEYS[target][0], kept)} & set(conflicts)


def values(name):
    return {(sid, start): value for sid, start, _e, _f, value, _s, _r in batch_for(name).obs}


def test_known_values_land_on_layout_series():
    cpi = values("cpi2024_current")
    assert cpi[("cpi.b2024.in.rural.general.index.m", date(2026, 7, 1))] == Decimal("108.34")
    assert cpi[("cpi.b2024.in.rural.general.infl_yoy.m", date(2026, 7, 1))] == Decimal("4.84")
    iip = values("iip_monthly_2022-23")
    assert iip[("iip.b2022_23.in.general.index.m", date(2026, 7, 1))] == Decimal("124.8")
    gdp = values("nas_c5_q_2022-23")
    assert gdp[("nas.b2022_23.in.gdp.current.q", date(2026, 4, 1))] == Decimal("8826871")
    assert gdp[("nas.b2022_23.in.gdp.constant.q", date(2026, 4, 1))] == Decimal("8136153")
    growth = values("nas_c22_q_2022-23")
    assert growth[("nas.b2022_23.in.gdp.growth_real.q", date(2026, 4, 1))] == Decimal("7.8")
    gva = values("nas_c1_a_2022-23")
    assert gva[("nas.b2022_23.in.gva.agri.current.a", date(2025, 4, 1))] == Decimal("5713629")


def test_energy_json_numbers_stay_exact_and_missing_values_are_skipped():
    assert (
        Decimal("141638.82") in values("energy_ind1_use1").values()
    )  # parse_float=Decimal, never float
    assert all(v is not None for v in values("rbi_47").values())  # '-' rows dropped


def test_api_labels_map_to_layout_tokens():
    from econdb.series_map import NIC_2DIGIT, slug

    assert mospi.geo("NCT of Delhi") == "in_dl"
    assert mospi.geo("The Dadra And Nagar Haveli And Daman And Diu") == "in_dh"
    assert {token for _, token in mospi.NIC_PREFIX} == {slug(label) for label in NIC_2DIGIT}
    api = "Manufacture of basic pharmaceutical products and pharmaceutical preparations"
    assert mospi.nic_token(api) == "pharmaceuticals"
    assert mospi.nic_token("Manufacture of Basic Metals") == "basic_metals"
    assert mospi.IIP_TOP[mospi.key("Electricity & Gas Supply")] == "electricity"


def test_discovered_ids_are_stable_and_distinct():
    assert mospi.dtoken("Food", "Cereals") == mospi.dtoken("Food", "Cereals")
    assert mospi.dtoken("Food", "Others") != mospi.dtoken("Clothing", "Others")


def test_dedupe_flags_conflicting_values():
    rows = [("s.in.x.m", date(2026, 1, 1), date(2026, 1, 31), "M", Decimal(1), None, "a")]
    same, conflict = rows + rows[:1], rows + [(*rows[0][:4], Decimal(2), None, "b")]
    assert mospi.dedupe(same, "obs") == (rows, [])
    assert mospi.dedupe(conflict, "obs") == ([], [("s.in.x.m", date(2026, 1, 1))])  # never guessed


def test_paging_stops_on_short_page(monkeypatch, tmp_path):
    monkeypatch.setenv("ECONDB_RAW_DIR", str(tmp_path))
    pages = [
        b'{"data":[%s],"meta_data":{"totalPages":2}}' % b",".join([b"{}"] * n) for n in (100, 7)
    ]
    calls = []

    def fake_get(url, params):
        calls.append(params["page"])
        return pages[params["page"] - 1]

    chunk = mospi.Chunk("RBI", "rbi/1", "/x", (("sub_indicator_code", 1),))
    got = list(mospi.fetch(chunk, "r1", get=fake_get))
    assert calls == [1, 2] and [len(rows) for _, rows, _ in got] == [100, 7]
    assert (tmp_path / got[0][0]).exists()  # archived before parsing


def test_stage_plans():
    today = date(2026, 9, 11)
    assert len(mospi.plan("CPI2024", today)) == 12 + 9
    assert len(mospi.plan("NAS", today)) == 88
    pilot = mospi.stage_chunks("pilot", today=today)
    assert {c.dataset for c in pilot} == {"NAS", "IIP", "RBI", "CPI2024"}
    assert sum(c.dataset in ("RBI", "CPI2024") for c in pilot) == 2
