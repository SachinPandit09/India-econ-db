"""MoSPI e-Sankhyiki API (incl. RBI datasets): chunk plan -> paged fetch -> normalise.

Called directly over HTTPS (not the mospi-esankhyiki package, which prints every response, parses
floats and drops meta_data). Values are strings or JSON numbers and are parsed to Decimal.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from econdb import archive, http, periods
from econdb.series_map import CPI_DIVISIONS, GVA_ANNUAL, GVA_QUARTERLY, IIP_ITEMS, STATES, slug

BASE = "https://api.mospi.gov.in"
PAGE = 100  # the API rejects larger pages


# ---- labels -> tokens ---------------------------------------------------------------------------


def key(text) -> str:
    """Normalised label for lookups: lower case, '&' -> 'and', punctuation -> spaces."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text).lower().replace("&", " and ")).split())


def key4(text) -> str:
    return " ".join(key(text).split()[:4])


def dtoken(*labels) -> str:
    """Stable token for a discovered line: slug of the last label + hash of the full path."""
    parts = [str(x).strip() for x in labels if x not in (None, "")]
    digest = hashlib.sha1(" > ".join(parts).encode()).hexdigest()[:6]
    return f"{slug(parts[-1])[:30].rstrip('_')}_{digest}"


GEO = {key(name): token for name, token in STATES.items()}
GEO["nct of delhi"] = "in_dl"


def geo(state) -> str:
    k = key(state).removeprefix("the ")  # 'The Dadra And Nagar Haveli And Daman And Diu'
    return GEO.get(k) or f"in_{slug(state)}"


# IIP NIC 2-digit: API 'Manufacture of Food Products' -> layout token (series_map.NIC_2DIGIT slugs)
NIC_PREFIX = [
    ("basic pharmaceutical", "pharmaceuticals"), ("basic metals", "basic_metals"),
    ("other non", "other_non_metallic_minerals"), ("other transport", "other_transport_equipment"),
    ("other manufacturing", "other_manufacturing"), ("food", "food_products"), ("beverages", "beverages"),
    ("tobacco", "tobacco_products"), ("textiles", "textiles"), ("wearing", "wearing_apparel"),
    ("leather", "leather_products"), ("wood", "wood_products"), ("paper", "paper_products"),
    ("printing", "printing_recorded_media"), ("coke", "coke_refined_petroleum"), ("chemicals", "chemicals"),
    ("rubber", "rubber_plastics"), ("fabricated", "fabricated_metal_products"),
    ("computer", "computer_electronic_optical"), ("electrical", "electrical_equipment"),
    ("machinery", "machinery_equipment_nec"), ("motor", "motor_vehicles_trailers"), ("furniture", "furniture"),
]  # fmt: skip


def nic_token(label) -> str | None:
    k = key(label).removeprefix("manufacture of ")
    return next((token for prefix, token in NIC_PREFIX if k.startswith(prefix)), None)


def base_token(base) -> str:
    return "b" + str(base).replace("-", "_")


def num(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal | int):
        return Decimal(value)
    text = str(value).strip().replace(",", "")
    if text in ("", "-", ".", "NA", "N.A.", "na", "..", "--"):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"not a number: {value!r}") from None


CPI24_DIVISION = {key4(label): token for label, token in CPI_DIVISIONS["2024"].items()}
CPI12_GROUP = {key4(label): token for label, token in CPI_DIVISIONS["2012"].items()}
CPI12_GROUP.update(
    {"general": "general", "general index": "general", "consumer food price": "cfpi"}
)
IIP_TOP = {key(label): token for label, token in IIP_ITEMS.items()}
IIP_TOP.update(
    {
        "mining and quarrying": "mining",
        "electricity and gas supply": "electricity",  # base 2022-23 name
        "infrastructure construction goods": "infra_construction_goods",
    }
)
WPI_TOP = {
    "wholesale price index": "all_commodities",
    "all commodities": "all_commodities",
    "primary articles": "primary_articles",
    "primary article": "primary_articles",
    "fuel and power": "fuel_power",
    "manufactured products": "manufactured_products",
    "wpi food index": "food_index",
    "food index": "food_index",
}
GVA_INDUSTRY = {key(label): token for label, token in {**GVA_ANNUAL, **GVA_QUARTERLY}.items()}
INSTITUTIONAL = {
    "public non financial corporations": "public_nfc",
    "private non financial corporations": "private_nfc",
    "public financial corporations": "public_fc",
    "private financial corporations": "private_fc",
    "general government": "general_govt",
    "households including npish": "households",
}
NAS_HEAD = {
    1: "gva", 2: "net_taxes", 3: "taxes", 4: "subsidies", 5: "gdp", 6: "cfc", 7: "ndp", 8: "gcf",
    9: "gfcf", 10: "pfce", 11: "gfce", 12: "change_in_stocks", 13: "valuables", 14: "exports",
    15: "imports", 16: "primary_income_row", 17: "gni", 18: "transfers_row", 19: "gndi", 20: "gds",
    21: "gva", 22: "gdp",
}  # fmt: skip
NAS_CATALOGUE = {1: "01-002", 5: "01-001", 21: "17-001", 22: "17-001"}
NAS_STAGE = {
    "first advance estimates": "advance_1",
    "second advance estimates": "advance_2",
    "provisional estimates": "provisional",
    "first revised estimates": "revised_1",
    "second revised estimates": "revised_2",
    "third revised estimates": "revised_3",
    "additional revision": "revised_4",
    "final estimates": "final",
}
CPI_STATUS = {"F": "final", "P": "provisional"}
PLFS_MEASURE = {
    1: "lfpr",
    2: "wpr",
    3: "ur",
    4: "wstatus",
    5: "jobq",
    6: "earn_regular",
    7: "earn_casual",
    8: "earn_self",
}
PLFS_AGE = {"15 years and above": "", "15-29 years": "_y1529"}
PLFS_SECTOR = {"rural": "rural", "urban": "urban", "rural urban": "total"}
PLFS_GENDER = {"male": "male", "female": "female", "person": "persons"}
PLFS_BREAKDOWN_OK = {None, "", "all", "All"}
PLFS_NOT_DIMS = {"year", "frequency", "value", "unit", "year_type", "indicator", "month"}
ASI_CORE = {
    "number of factories": "factories.count",
    "fixed capital": "fixed_capital.inr",
    "invested capital": "invested_capital.inr",
    "workers": "workers.count",
    "total persons engaged": "persons_engaged.count",
    "wages to workers": "wages_workers.inr",
    "total output": "output.inr",
    "total input": "input.inr",
    "gross value added": "gva.inr",
    "profits": "profits.inr",
}
MNRE_TYPE = {"solar power": "solar", "wind power": "wind", "small hydro power": "hydro", "hydro power": "hydro",
             "bio power": "bio", "total power": "total"}  # fmt: skip
FX_RESERVES = {"total": "total", "foreign currency assets": "fca", "gold": "gold", "sdrs": "sdr",
               "reserve tranche position": "rtp"}  # fmt: skip

# RBI sub_indicator_code -> (series family, period rule, amount measure; None = read from unit/labels)
RBI = {
    1: ("trade", "fy", "inr"), 11: ("trade", "fy", "usd"), 2: ("trade", "fy", "inr"), 20: ("trade", "fy", "usd"),
    4: ("bop", "fyq", "usd"), 10: ("bop", "fyq", "inr"), 5: ("bop", "fy", "usd"), 6: ("bop", "fy", "inr"),
    7: ("bop", "fy", "inr"), 8: ("bop", "fy", "usd"), 9: ("bop", "fy", "usd"), 14: ("bop", "fy", "inr"),
    22: ("bop", "fy", "pct"), 12: ("trade", "fym", "usd"), 13: ("trade", "fym", "inr"),
    16: ("trade", "fy", "usd"), 17: ("trade", "fy", "inr"), 24: ("trade", "fym", "inr"), 42: ("trade", "fym", "usd"),
    43: ("trade", "fy", "inr"), 44: ("trade", "fy", "usd"), 45: ("trade", "fy", "inr"), 46: ("trade", "fy", "usd"),
    25: ("extdebt", "endmar", "usd"), 26: ("extdebt", "endmar", "inr"), 27: ("extdebt", "qmonth", None),
    28: ("fx_ops", "month", None), 29: ("fxrate", "month", "rate"), 30: ("fx_turnover", "fym", "usd"),
    31: ("fxrate", "fy", "rate"), 32: ("fxrate", "cy", "rate"), 33: ("fxrate", "month", "rate"),
    34: ("fwd_premia", "month", "rate"), 35: ("fxrate", "month", "rate"), 36: ("fxrate", "month", "rate"),
    37: ("fxrate", "month", "rate"), 40: ("nri_dep", "fym", "usd"), 47: ("fxres", "month", None),
    48: ("fxres", "fy", None),
}  # fmt: skip
RBI_CATALOGUE = {"trade": "08-001", "bop": "08-007", "extdebt": "08-011", "fxres": "08-012", "fx_ops": "08-013",
                 "fwd_premia": "08-014", "fxrate": "08-015", "fx_turnover": "08-018", "nri_dep": "08-019"}  # fmt: skip
RBI_NOT_DIMS = {"indicator", "year", "month", "quarter", "value", "unit"}
STOCK_FAMILIES = {"extdebt", "fxres"}


# ---- chunks ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    dataset: str
    key: str
    path: str
    params: tuple  # sorted (name, value) pairs, hashable

    @property
    def query(self) -> dict:
        return dict(self.params)


def _chunk(dataset, key_, path, **params) -> Chunk:
    return Chunk(dataset, key_, path, tuple(sorted(params.items())))


def plan(dataset: str, today: date | None = None) -> list[Chunk]:
    """Every query needed for a full-history backfill of one dataset."""
    today = today or date.today()
    y = today.year
    fy_now = y if today.month >= 4 else y - 1
    c = []
    if dataset == "CPI2024":
        for year in range(2025, y + 1):
            for m in range(1, 13 if year < y else today.month + 1):
                c.append(_chunk(dataset, f"cpi2024/Current/{year}-{m:02d}", "/api/cpi/getCPIData",
                                base_year="2024", series="Current", year=str(year), month_code=m))  # fmt: skip
    elif dataset == "CPI2024BACK":
        for year in range(2013, 2025):
            c.append(_chunk(dataset, f"cpi2024/Back/{year}", "/api/cpi/getCPIData", base_year="2024",
                            series="Back", year=str(year)))  # fmt: skip
    elif dataset in ("CPI2012", "CPI2010"):
        base = dataset[3:]
        for year in range(2011, y + 1) if base == "2012" else range(2011, 2015):
            c.append(_chunk(dataset, f"cpi{base}/group/{year}", "/api/cpi/getCPIIndex", base_year=base,
                            series="Current", year=str(year)))  # fmt: skip
    elif dataset == "CPI2012ITEM":
        for year in range(2014, y + 1):
            c.append(_chunk(dataset, f"cpi2012/item/{year}", "/api/cpi/getItemIndex", base_year="2012",
                            series="Current", year=str(year)))  # fmt: skip
    elif dataset == "WPI":
        for base, first, last in (("2022-23", 2023, y), ("2011-12", 2012, y), ("2004-05", 2005, 2017),
                                  ("1993-94", 1994, 2010)):  # fmt: skip
            for year in range(first, last + 1):
                c.append(
                    _chunk(
                        dataset,
                        f"wpi/{base}/{year}",
                        "/api/wpi/getWpiRecords",
                        base_year=base,
                        year=year,
                    )
                )
    elif dataset == "IIP":
        for base in ("2022-23", "2011-12", "2004-05", "1993-94"):
            c.append(_chunk(dataset, f"iip/{base}/M", "/api/iip/getIIPMonthly", base_year=base,
                            frequency="Monthly", type="All"))  # fmt: skip
            c.append(_chunk(dataset, f"iip/{base}/A", "/api/iip/getIIPAnnual", base_year=base,
                            frequency="Annually", type="All"))  # fmt: skip
    elif dataset == "NAS":
        for code in range(1, 23):
            for base in ("2022-23", "2011-12"):
                for fc in (1, 2):
                    c.append(_chunk(dataset, f"nas/{code}/{base}/{'AQ'[fc - 1]}", "/api/nas/getNASData",
                                    base_year=base, series="Current", frequency_code=fc, indicator_code=code))  # fmt: skip
    elif dataset == "PLFS":
        ay_years = [f"{a}-{(a + 1) % 100:02d}" for a in range(2017, fy_now)]
        for ind in range(1, 9):
            for label in ay_years:
                c.append(_chunk(dataset, f"plfs/A/AY/{ind}/{label}", "/api/plfs/getData", indicator_code=ind,
                                frequency_code=1, year_type_code=1, year=label))  # fmt: skip
            for year in range(2022, y + 1):
                c.append(_chunk(dataset, f"plfs/A/CY/{ind}/{year}", "/api/plfs/getData", indicator_code=ind,
                                frequency_code=1, year_type_code=2, year=str(year)))  # fmt: skip
        for ind in range(
            1, 5
        ):  # quarterly bulletin: no year_type_code (it returns nothing with one)
            for year in range(2018, y + 1):
                c.append(_chunk(dataset, f"plfs/Q/{ind}/{year}", "/api/plfs/getData", indicator_code=ind,
                                frequency_code=2, year=str(year)))  # fmt: skip
        for ind in range(1, 4):
            c.append(
                _chunk(
                    dataset,
                    f"plfs/M/{ind}",
                    "/api/plfs/getData",
                    indicator_code=ind,
                    frequency_code=3,
                )
            )
    elif dataset == "RBI":
        for code in sorted(RBI):
            c.append(
                _chunk(dataset, f"rbi/{code}", "/api/rbi/getRbiRecords", sub_indicator_code=code)
            )
    elif dataset == "CPIALRL":
        for ind in (1, 2):
            c.append(
                _chunk(
                    dataset, f"cpialrl/{ind}", "/api/cpialrl/getCpialrlRecords", indicator_code=ind
                )
            )
    elif dataset == "ASI":
        for cls, first, last in ((2008, 2008, 2023), (2004, 2004, 2007)):
            for a in range(first, last + 1):
                label = f"{a}-{(a + 1) % 100:02d}"
                c.append(_chunk(dataset, f"asi/{cls}/{label}", "/api/asi/getASIData", classification_year=cls,
                                sector_code="Combined", nic_type="All", state_code=99, year=label))  # fmt: skip
    elif dataset == "ENERGY":
        for ind in (1, 2):
            for use in (1, 2):
                c.append(_chunk(dataset, f"energy/{ind}/{use}", "/api/energy/getEnergyRecords", indicator_code=ind,
                                use_of_energy_balance_code=use))  # fmt: skip
    elif dataset == "MNRE":
        for t in range(1, 6):
            c.append(
                _chunk(
                    dataset,
                    f"mnre/{t}",
                    "/api/mnre/getDataByEnergy",
                    type_of_renewable_energy_code=t,
                )
            )
    elif dataset == "ISP":
        for fc in (1, 2):
            c.append(_chunk(dataset, f"isp/{fc}", "/api/isp/getISPRecords", frequency_code=fc))
    elif dataset in ("HCES", "NFHS"):
        path = "/api/hces/getHcesRecords" if dataset == "HCES" else "/api/nfhs/getNfhsRecords"
        for ind in range(1, 10 if dataset == "HCES" else 22):
            c.append(_chunk(dataset, f"{dataset.lower()}/{ind}", path, indicator_code=ind))
    else:
        raise ValueError(f"unknown MoSPI dataset {dataset!r}")
    return c


DATASETS = ["CPI2024", "CPI2024BACK", "CPI2012", "CPI2012ITEM", "CPI2010", "WPI", "IIP", "NAS", "PLFS", "RBI",
            "CPIALRL", "ASI", "ENERGY", "MNRE", "ISP", "HCES", "NFHS"]  # fmt: skip
STAGES = {
    "pilot": ["NAS", "IIP", "RBI", "CPI2024"],
    "A": [d for d in DATASETS if d not in ("CPI2024", "ASI")],
    "B": ["CPI2024"],
    "C": ["ASI"],
    "all": DATASETS,
}
PILOT_KEYS = {"rbi/47", "cpi2024/Current/2026-07"}  # plus every NAS and IIP chunk


def stage_chunks(
    stage: str, datasets: list[str] | None = None, today: date | None = None
) -> list[Chunk]:
    chunks = [ch for d in (datasets or STAGES[stage]) for ch in plan(d, today)]
    if stage == "pilot" and not datasets:
        chunks = [ch for ch in chunks if ch.dataset in ("NAS", "IIP") or ch.key in PILOT_KEYS]
    return chunks


# ---- fetch ---------------------------------------------------------------------------------------


def count(chunk: Chunk, get=http.get) -> int:
    """totalRecords for a chunk (one 10-row request)."""
    doc = json.loads(
        get(BASE + chunk.path, {**chunk.query, "Format": "JSON", "limit": 10, "page": 1})
    )
    return int((doc.get("meta_data") or {}).get("totalRecords") or 0)


def safe_key(chunk_key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", chunk_key)


def fetch(chunk: Chunk, run_tag: str, get=http.get, on_page=None):
    """Yield (raw_ref, rows, meta) per page; every body is archived before it is parsed."""
    page, pages = 1, None
    while pages is None or page <= pages:
        body = get(
            BASE + chunk.path, {**chunk.query, "Format": "JSON", "limit": PAGE, "page": page}
        )
        name = f"{run_tag}_{safe_key(chunk.key)}_p{page:05d}.json.gz"
        ref = archive.save(f"mospi/{chunk.dataset}/{date.today():%Y-%m-%d}/{name}", body)
        rows, meta = parse(body, chunk.key)
        pages = pages or int(meta.get("totalPages") or 0)
        if on_page:
            on_page(page, pages, len(rows))
        yield ref, rows, meta
        if len(rows) < PAGE:
            break
        page += 1


def parse(body: bytes, where: str = "") -> tuple[list, dict]:
    doc = json.loads(body, parse_float=Decimal)
    if doc.get("statusCode") is False and doc.get("msg") != "No Data Found":
        raise ValueError(f"{where}: API error {doc.get('message') or doc.get('msg')}")
    rows = doc.get("data") if isinstance(doc.get("data"), list) else []
    return rows, doc.get("meta_data") or {}


# ---- normalise -------------------------------------------------------------------------------------


@dataclass
class Batch:
    obs: list = field(default_factory=list)  # (series_id, start, end, freq, value, stage, raw_ref)
    series: dict = field(default_factory=dict)  # discovered series_id -> meta.series row
    cpi: list = field(default_factory=list)  # raw.cpi_detail rows
    detail: list = field(default_factory=list)  # raw.mospi_detail rows
    bad_rows: list = field(
        default_factory=list
    )  # rows that could not be normalised (skipped, logged)
    rows_in: int = 0


# (key, compared value) per target table, for dedupe inside one chunk
KEYS = {
    "obs": (lambda r: (r[0], r[1]), lambda r: (r[4], r[5])),
    "cpi": (lambda r: (*r[:5], r[7]), lambda r: (r[8], r[9], r[11])),
    "detail": (
        lambda r: (r[0], r[1], json.dumps(r[2], sort_keys=True), r[3], r[4], r[5]),
        lambda r: r[6],
    ),
}

UNIT = {  # measure token -> (unit, scale, currency, agg_rule)
    "index": ("index", None, None, "mean"),
    "infl_yoy": ("percent", None, None, "recompute"),
    "growth_yoy": ("percent", None, None, "recompute"),
    "growth_real": ("percent", None, None, "recompute"),
    "growth_nominal": ("percent", None, None, "recompute"),
    "usd": ("amount", "million", "USD", "sum"),
    "inr": ("amount", "crore", "INR", "sum"),
    "sdr": ("amount", "million", "XDR", "sum"),
    "pct": ("percent", None, None, "recompute"),
    "rate": ("rate", None, None, "mean"),
}


def add(b: Batch, sid: str, span, value, stage, ref, *, dataset, name, unit=None, base=None, catalogue=None,
        dims=None, params=None, period_basis="FY", agg=None, scale=None, currency=None, price_basis=None):  # fmt: skip
    v = num(value)
    if v is None:
        return
    b.obs.append((sid, span[0], span[1], sid[-1].upper(), v, stage, ref))
    if sid not in b.series:
        u = UNIT.get(sid.split(".")[-2], ("value", None, None, "none"))
        b.series[sid] = {
            "series_id": sid, "source_id": "mospi", "catalogue_id": catalogue, "family": sid.split(".")[0],
            "name": name, "dataset": dataset, "dimensions": dims or {}, "unit": unit or u[0],
            "scale": scale if scale is not None else u[1], "currency": currency or u[2], "price_basis": price_basis,
            "freq": sid[-1].upper(), "period_basis": period_basis, "base_year": base,
            "agg_rule": agg or u[3], "source_params": params or {},
        }  # fmt: skip


def normalise(chunk: Chunk, pages) -> Batch:
    """pages: iterable of (raw_ref, rows, meta)."""
    b = Batch()
    fn = NORMALISERS[chunk.dataset]
    for ref, rows, _ in pages:
        b.rows_in += len(rows)
        for i, r in enumerate(rows):
            row_ref = f"{ref}#{i}"  # archive file + row position inside it
            try:
                fn(chunk, r, row_ref, b)
            except (ValueError, KeyError) as e:  # e.g. NAS code 19 lists a stray year '1999'
                b.bad_rows.append(
                    {"error": str(e), "row": {k: str(v) for k, v in r.items()}, "raw_ref": row_ref}
                )
    if chunk.dataset == "NAS":  # some codes list every estimate stage; core keeps the most advanced
        best = {}
        for o in b.obs:
            k = (o[0], o[1])
            if k not in best or STAGE_RANK.get(o[5], -1) > STAGE_RANK.get(best[k][5], -1):
                best[k] = o
        b.obs = list(best.values())
    return b


STAGE_RANK = {s: i for i, s in enumerate(
    ["advance_1", "advance_2", "provisional", "revised_1", "revised_2", "revised_3", "revised_4", "final"])}  # fmt: skip


def _cpi2024(ch, r, ref, b):
    back = r.get("series") == "Back"
    span = periods.month(r["year"], r["month"])
    path = [r[k] for k in ("division", "group", "class", "sub_class", "item") if r.get(k)]
    level = ("division", "group", "class", "sub_class", "item")[len(path) - 1]
    line = " > ".join(path)
    b.cpi.append(("2024", r["series"], r["state"], r["sector"], line, level, r.get("code"), span[0],
                  num(r.get("index")), num(r.get("inflation")), r.get("imputation"), None, ref))  # fmt: skip
    all_india = r["state"] == "All India"
    if not all_india and level != "division":
        return  # states: curated core down to division level only
    if level == "division":
        tok = CPI24_DIVISION.get(key4(path[0])) or dtoken(*path)
        cat = "02-001" if tok == "general" and all_india else "02-002" if all_india else "02-005"
    else:
        tok = "c" + r["code"].replace(".", "_") if r.get("code") else dtoken(*path)
        cat = "02-004" if level == "item" else "02-003"
    for col, measure in (("index", "index"), ("inflation", "infl_yoy")):
        sid = f"cpi.{'b2024_back' if back else 'b2024'}.{geo(r['state'])}.{r['sector'].lower()}.{tok}.{measure}.m"
        add(b, sid, span, r.get(col), None, ref, dataset="CPI", base="2024", catalogue=cat,
            name=f"CPI (2024=100{', back series' if back else ''}) · {r['state']} · {r['sector']} · {line} · {col}",
            dims={"state": r["state"], "sector": r["sector"], "line": line, "code": r.get("code")},
            params={"base_year": "2024", "series": r["series"]})  # fmt: skip


def _cpi_group(ch, r, ref, b):
    base = str(r.get("baseyear") or ch.query["base_year"])
    span = periods.month(r["year"], r["month"])
    group, sub = r.get("group"), r.get("subgroup")
    overall = not sub or key(sub).endswith("overall") or key(sub) == key(group)
    path = [group] if overall else [group, sub]
    line = " > ".join(path)
    b.cpi.append((base, "Current", r["state"], r["sector"], line, "group" if overall else "subgroup", None,
                  span[0], num(r.get("index")), num(r.get("inflation")), None, r.get("status"), ref))  # fmt: skip
    if r["state"] != "All India" and not overall:
        return
    tok = (CPI12_GROUP.get(key4(group)) if overall else None) or dtoken(*path)
    for col, measure in (("index", "index"), ("inflation", "infl_yoy")):
        sid = f"cpi.b{base}.{geo(r['state'])}.{r['sector'].lower()}.{tok}.{measure}.m"
        add(b, sid, span, r.get(col), CPI_STATUS.get(r.get("status")), ref, dataset="CPI", base=base,
            catalogue={"2012": "02-006", "2010": "02-007"}[base],
            name=f"CPI ({base}=100) · {r['state']} · {r['sector']} · {line} · {col}",
            dims={"state": r["state"], "sector": r["sector"], "line": line}, params={"base_year": base})  # fmt: skip


def _cpi_item(ch, r, ref, b):
    span = periods.month(r["year"], r["month"])
    b.cpi.append(("2012", "Current", "All India", "", r["item"], "item", None, span[0], num(r.get("index")),
                  num(r.get("inflation")), None, r.get("status"), ref))  # fmt: skip
    for col, measure in (("index", "index"), ("inflation", "infl_yoy")):
        add(b, f"cpi.b2012.in.{dtoken(r['item'])}.{measure}.m", span, r.get(col), CPI_STATUS.get(r.get("status")),
            ref, dataset="CPI", base="2012", catalogue="02-006", name=f"CPI (2012=100) item · {r['item']} · {col}",
            dims={"item": r["item"]}, params={"base_year": "2012", "endpoint": "item"})  # fmt: skip


WPI_LEVELS = (("major_group", "majorgroup"), ("group",), ("sub_group", "subgroup"),
              ("sub_sub_group", "sub_subgroup"), ("item",))  # fmt: skip


def _wpi(ch, r, ref, b):
    base = ch.query["base_year"]
    path = [
        str(v).strip()
        for v in (next((r[k] for k in names if r.get(k)), None) for names in WPI_LEVELS)
        if v
    ]
    tok = (WPI_TOP.get(key(path[0])) if len(path) == 1 else None) or dtoken(*path)
    line = " > ".join(path)
    add(b, f"wpi.{base_token(base)}.in.{tok}.index.m", periods.month(r["year"], r["month"]), r.get("index_value"),
        None, ref, dataset="WPI", base=base, catalogue={"2022-23": "02-012", "2011-12": "02-014"}.get(base, "02-015"),
        name=f"WPI ({base}=100) · {line}", dims={"line": line}, params={"base_year": base})  # fmt: skip


def _iip(ch, r, ref, b):
    base, monthly = ch.query["base_year"], ch.query["frequency"] == "Monthly"
    span = periods.month(r["year"], r["month"]) if monthly else periods.fy(r["year"])
    cat, sub = r.get("category"), r.get("sub_category")
    if not sub:
        tok = IIP_TOP.get(key(cat)) or dtoken(cat)
    elif key(cat) == "manufacturing":
        tok = "mfg." + (nic_token(sub) or dtoken(sub))
    else:
        tok = dtoken(cat, sub)
    for col, measure in (("index", "index"), ("growth_rate", "growth_yoy")):
        add(b, f"iip.{base_token(base)}.in.{tok}.{measure}.{'m' if monthly else 'a'}", span, r.get(col), None, ref,
            dataset="IIP", base=base, catalogue="03-001" if base == "2022-23" else "03-005",
            name=f"IIP ({base}=100) · {r.get('type')} · {cat}{' > ' + sub if sub else ''} · {col}",
            dims={"type": r.get("type"), "category": cat, "sub_category": sub}, params={"base_year": base})  # fmt: skip


def _nas(ch, r, ref, b):
    q = ch.query
    base, code, quarterly = q["base_year"], q["indicator_code"], q["frequency_code"] == 2
    span = periods.fy_quarter(r["year"], r["quarter"]) if quarterly else periods.fy(r["year"])
    head = NAS_HEAD[code]
    ind, sub, inst = r.get("industry"), r.get("subindustry"), r.get("institutional_sector")
    if inst:
        subject = f"{head}_inst.{INSTITUTIONAL.get(key(inst)) or dtoken(inst)}"
    elif sub:
        subject = f"{head}.{dtoken(ind, sub)}"
    elif ind:
        subject = f"{head}.{GVA_INDUSTRY.get(key(ind)) or dtoken(ind)}"
    else:
        subject = head
    unit = (r.get("unit") or "").lower()
    scale = "lakh" if "lakh" in unit else "crore" if "crore" in unit else None
    growth = code in (21, 22)
    stage = NAS_STAGE.get(key(r.get("revision") or ""))
    breakdown = " > ".join(x for x in (ind, sub, inst) if x) or "total"
    detail = {k: v for k, v in (("industry", ind), ("subindustry", sub), ("institutional_sector", inst),
                                ("revision", r.get("revision"))) if v}  # fmt: skip
    for col in (
        "current_price",
        "constant_price",
    ):  # every stage kept in raw (core keeps the latest)
        if (v := num(r.get(col))) is not None:
            b.detail.append(("NAS", f"{code}/{base}/{'Q' if quarterly else 'A'}", detail, col, span[0], span[1],
                             v, r.get("unit"), ref))  # fmt: skip
    for col, measure in (("current_price", "current"), ("constant_price", "constant")):
        m = ("growth_nominal" if measure == "current" else "growth_real") if growth else measure
        sid = f"nas.{base_token(base)}.in.{subject}.{m}.{'q' if quarterly else 'a'}"
        add(b, sid, span, r.get(col), stage, ref, dataset="NAS", base=base, catalogue=NAS_CATALOGUE.get(code),
            unit="percent" if growth else "amount", scale=None if growth else scale,
            currency=None if growth else "INR", price_basis=None if growth else measure,
            agg="recompute" if growth else "sum", name=f"{r.get('indicator')} ({base} base) · {breakdown} · {col}",
            dims={"indicator_code": code, "industry": ind, "subindustry": sub, "institutional_sector": inst},
            params={"indicator_code": code, "base_year": base, "frequency_code": q["frequency_code"]})  # fmt: skip


def _plfs(ch, r, ref, b):
    q = ch.query
    ind, fc, yt = q["indicator_code"], q["frequency_code"], q.get("year_type_code")
    quarter = r.get("quarter")
    if fc == 3:
        span, freq = periods.month(r["year"], r["month"]), "m"
    elif fc == 2:
        span, freq = periods.named_quarter(r["year"], quarter), "q"
    elif quarter and key(quarter) != "all":
        span = (
            periods.ay_quarter(r["year"], quarter)
            if yt == 1
            else periods.named_quarter(r["year"], quarter)
        )
        freq = "q"
    else:
        span, freq = (periods.ay(r["year"]) if yt == 1 else periods.cy(r["year"])), "a"
    value = num(r.get("value"))
    if value is None:
        return
    dims = {k: v for k, v in r.items() if k not in PLFS_NOT_DIMS and v not in (None, "")}
    year_type = {1: "AY", 2: "CY"}.get(yt, "-")
    b.detail.append(("PLFS", f"{'AQM'[fc - 1]}/{year_type}/{ind}", dims, "value", span[0], span[1], value,
                     r.get("unit"), ref))  # fmt: skip
    # curated core: All-India + states, sector x gender, age 15+ / 15-29, no other breakdown
    age = PLFS_AGE.get(r.get("AgeGroup") or "15 years and above")
    sector, gender = (
        PLFS_SECTOR.get(key(r.get("sector") or "")),
        PLFS_GENDER.get(key(r.get("gender") or "")),
    )
    status = r.get("broad_status_employment")
    core_dims = (
        "state",
        "sector",
        "gender",
        "AgeGroup",
        "weekly_status",
        "quarter",
        "broad_status_employment",
    )
    others = [v for k, v in dims.items() if k not in core_dims]
    if (
        age is None
        or sector is None
        or gender is None
        or any(v not in PLFS_BREAKDOWN_OK for v in others)
    ):
        return
    if ind != 4 and status not in PLFS_BREAKDOWN_OK:
        return
    weekly = key(r.get("weekly_status") or "")
    approach = {"ps ss": "_us", "cws": "_cws"}.get(weekly, "_cws" if fc > 1 else "")
    status_tok = f"_{dtoken(status)}" if ind == 4 and status not in PLFS_BREAKDOWN_OK else ""
    measure = (
        f"{PLFS_MEASURE[ind]}{status_tok}{approach}{age}{'_cy' if yt == 2 and freq == 'a' else ''}"
    )
    sid = f"plfs.{geo(r['state'])}.{sector}.{gender}.{measure}.{freq}"
    label = " · ".join(str(x) for x in (r.get("indicator"), r["state"], r.get("sector"), r.get("gender"),
                                        r.get("AgeGroup"), r.get("weekly_status"), status) if x)  # fmt: skip
    add(b, sid, span, value, None, ref, dataset="PLFS", unit="percent" if r.get("unit") == "%" else r.get("unit"),
        catalogue={1: "05-002", 2: "05-003", 3: "05-001", 4: "05-004"}.get(ind, "05-006"), agg="none",
        period_basis=year_type if freq == "a" else "FY", name=f"PLFS · {label}", dims=dims,
        params={"indicator_code": ind, "frequency_code": fc, "year_type_code": yt})  # fmt: skip


def _cpialrl(ch, r, ref, b):
    base = {"1986-1987": "1986-87"}.get(str(r["base_year"]), str(r["base_year"]))
    y = str(r["year"])
    span = periods.fy_month(y, r["month"]) if "-" in y else periods.month(y, r["month"])
    group = r.get("group")
    item = "general" if not group else ("food" if key(group).startswith("food") else dtoken(group))
    for col, family, measure in (("index_al", "cpi_al", "index"), ("index_rl", "cpi_rl", "index"),
                                 ("inflation_al", "cpi_al", "infl_yoy"), ("inflation_rl", "cpi_rl", "infl_yoy")):  # fmt: skip
        add(b, f"{family}.{base_token(base)}.{geo(r['state'])}.{item}.{measure}.m", span, r.get(col), None, ref,
            dataset="CPIALRL", base=base, catalogue="02-010",
            name=f"CPI-{family[-2:].upper()} ({base}=100) · {r['state']} · {group or 'General'} · {col}",
            dims={"state": r["state"], "group": group}, params={"indicator_code": ch.query["indicator_code"]})  # fmt: skip


def _asi(ch, r, ref, b):
    cls = ch.query["classification_year"]
    span = periods.fy(r["year"])
    value = num(r.get("value"))
    if value is None:
        return
    dims = {
        k: r.get(k)
        for k in ("state", "sector", "indicator", "nic_code", "nic_description", "nic_type")
    }
    b.detail.append(
        ("ASI", f"NIC{cls}", dims, "value", span[0], span[1], value, r.get("unit"), ref)
    )
    if (
        r.get("state") == "All India"
        and str(r.get("nic_code")) == "99999"
        and r.get("nic_type") == "2-digit"
    ):
        unit = r.get("unit") or "-"
        money = "₹" in unit or "lakh" in unit.lower()
        tok = (
            ASI_CORE.get(key(r["indicator"]))
            or f"{dtoken(r['indicator'])}.{'inr' if money else 'value'}"
        )
        inr = tok.endswith(".inr")
        add(b, f"asi.in.{tok}.a", span, value, None, ref, dataset="ASI", catalogue="03-009", agg="none",
            unit="amount" if inr else "number", scale="lakh" if inr else None, currency="INR" if inr else None,
            name=f"ASI · All India · {r['indicator']}", dims={"indicator": r["indicator"]},
            params={"classification_year": cls})  # fmt: skip


def _energy(ch, r, ref, b):
    unit = "ktoe" if ch.query["indicator_code"] == 1 else "pj"
    path = [
        r.get(k)
        for k in (
            "energy_commodities",
            "energy_sub_commodities",
            "end_use_sector",
            "end_use_sub_sector",
        )
    ]
    labels = [str(x).strip() for x in path if x not in (None, "")]
    add(b, f"energy.in.{slug(r['use_of_energy_balance'])}.{dtoken(*labels)}.{unit}.a", periods.fy(r["year"]),
        r.get("value"), None, ref, dataset="ENERGY", catalogue="11-009", unit=unit.upper(), agg="none",
        name=f"Energy balance · {r['use_of_energy_balance']} · {' > '.join(labels)} · {unit}",
        dims={"use": r["use_of_energy_balance"], "path": labels}, params=ch.query)  # fmt: skip


def _mnre(ch, r, ref, b):
    kind = r["type_of_renewable_energy"]
    t = MNRE_TYPE.get(key(kind)) or dtoken(kind)
    subject = f"{t}.{dtoken(r['category'])}" if r.get("category") else t
    add(b, f"re_cap.{geo(r['state'])}.{subject}.mw.m", periods.month(r["year"], r["month"]), r.get("value"), None,
        ref, dataset="MNRE", catalogue="11-005", unit="MW", agg="end",
        name=f"Renewable capacity · {r['state']} · {kind}{' · ' + r['category'] if r.get('category') else ''}",
        dims={"state": r["state"], "type": kind, "category": r.get("category")}, params=ch.query)  # fmt: skip


def _isp(ch, r, ref, b):
    base, monthly = str(r["base_year"]), r.get("frequency") == "Monthly"
    span = periods.fy_month(r["year"], r["month"]) if monthly else periods.fy(r["year"])
    sub = r["broad_sub_sector"]
    tok = "overall" if key(sub) in ("overall", "services", "overall index", "isp") else dtoken(sub)
    for col, measure in (("index", "index"), ("growth_rate", "growth_yoy")):
        add(b, f"isp.{base_token(base)}.in.{tok}.{measure}.{'m' if monthly else 'a'}", span, r.get(col), None, ref,
            dataset="ISP", base=base, catalogue="03-008", name=f"ISP ({base}=100) · {sub} · {col}",
            dims={"broad_sub_sector": sub}, params=ch.query)  # fmt: skip


def _survey(ch, r, ref, b):
    dataset = ch.dataset
    span = periods.survey(dataset, r["year"] if dataset == "HCES" else r["survey"])
    value = num(r.get("value"))
    if value is None:
        return
    dims = {
        k: v
        for k, v in r.items()
        if k not in ("year", "value", "unit", "survey") and v not in (None, "")
    }
    b.detail.append((dataset, f"ind{ch.query['indicator_code']}", dims, "value", span[0], span[1], value,
                     r.get("unit"), ref))  # fmt: skip
    if r.get("state") != "All India":
        return
    sector = key(r.get("sector") or "")
    sector_tok = "" if "combined" in sector or not sector else f"{slug(sector)}."
    if dataset == "HCES" and ch.query["indicator_code"] == 1:
        tok = "mpce_imputed" if key(r.get("imputation_type") or "") == "with imputation" else "mpce"
    else:
        tok = dtoken(*[v for k, v in dims.items() if k not in ("state", "sector")])
    label = " · ".join(str(v) for k, v in dims.items() if k != "state")
    add(b, f"{dataset.lower()}.in.{sector_tok}{tok}.o", span, value, None, ref, dataset=dataset,
        catalogue="14-001" if dataset == "HCES" else "14-002", unit=r.get("unit") or "value", agg="none",
        period_basis=None, name=f"{dataset} · All India · {label}", dims=dims, params=ch.query)  # fmt: skip


def _rbi(ch, r, ref, b):
    code = ch.query["sub_indicator_code"]
    family, rule, money = RBI[code]
    year = str(r["year"]).strip()
    span = {
        "fy": lambda: periods.fy(year),
        "fyq": lambda: periods.fy_quarter(year, r["quarter"]),
        "fym": lambda: periods.fy_month(year, r["month"]),
        "month": lambda: periods.month(year, r["month"]),
        "qmonth": lambda: periods.quarter_of_month(year, r["month"]),
        "endmar": lambda: periods.end_march(year),
        "cy": lambda: periods.cy(year),
    }[rule]()
    dims = {
        k: str(v).strip() for k, v in r.items() if k not in RBI_NOT_DIMS and v not in (None, "")
    }
    unit = str(r.get("unit") or "").strip()
    if money is None:  # measure from the unit or currency label
        text = " ".join([unit, *dims.values()]).lower()
        usd = "us $" in text or "us$" in text
        money = (
            "usd"
            if usd
            else "sdr"
            if "sdrs millions" in text
            else "inr"
            if "₹" in text or "crore" in text
            else "value"
        )  # noqa: E501
    parts = [v for k, v in dims.items() if k != "foreign_exchange_reserve_currency"]
    if family == "fxres":
        subject = FX_RESERVES.get(key(dims.get("foreign_exchange_reserve_type", ""))) or dtoken(
            *parts
        )
    else:
        subject = dtoken(*parts) if parts else "total"
    freq = {"fy": "a", "endmar": "a", "cy": "a", "fyq": "q", "qmonth": "q"}.get(rule, "m")
    agg = "end" if family in STOCK_FAMILIES or "outstanding" in " ".join(parts).lower() else None
    add(b, f"{family}.in.{subject}.{money}.{freq}", span, r.get("value"), None, ref, dataset="RBI",
        catalogue=RBI_CATALOGUE.get(family), agg=agg, unit=unit or None, period_basis="CY" if rule == "cy" else "FY",
        name=f"RBI {code} · {str(r.get('indicator') or '').strip()} · {' > '.join(parts)} · {unit}",
        dims={"sub_indicator_code": code, **dims}, params={"sub_indicator_code": code})  # fmt: skip


NORMALISERS = {
    "CPI2024": _cpi2024, "CPI2024BACK": _cpi2024, "CPI2012": _cpi_group, "CPI2010": _cpi_group,
    "CPI2012ITEM": _cpi_item, "WPI": _wpi, "IIP": _iip, "NAS": _nas, "PLFS": _plfs, "RBI": _rbi,
    "CPIALRL": _cpialrl, "ASI": _asi, "ENERGY": _energy, "MNRE": _mnre, "ISP": _isp, "HCES": _survey,
    "NFHS": _survey,
}  # fmt: skip


def dedupe(rows: list, target: str) -> tuple[list, list, list]:
    """Drop exact duplicates inside one chunk. Keys whose rows disagree on the value are ambiguous
    in the source (e.g. WPI 1993-94 repeats a label with different values): they are never guessed
    into the target. Returns (clean rows, conflicting keys, every row of those keys)."""
    keyfn, valuefn = KEYS[target]
    first, conflicts = {}, set()
    for row in rows:
        k, v = keyfn(row), valuefn(row)
        if first.setdefault(k, v) != v:
            conflicts.add(k)
    seen, out, ambiguous = set(), [], []
    for row in rows:
        k = keyfn(row)
        if k in conflicts:
            ambiguous.append(row)
        elif k not in seen:
            seen.add(k)
            out.append(row)
    return out, sorted(conflicts, key=str), ambiguous


def ambiguous_detail(target: str, rows: list, series: dict) -> list:
    """Keep ambiguous source rows in raw.mospi_detail, flagged {"ambiguous": true, "occurrence": n}
    (excluded from core); raw_ref holds the archive file and row position ('...json.gz#17')."""
    keyfn = KEYS[target][0]
    seen, out = {}, []
    for row in rows:
        k = keyfn(row)
        seen[k] = seen.get(k, 0) + 1
        flag = {"ambiguous": True, "occurrence": seen[k]}
        if target == "detail":
            dataset, variant, dims, measure, start, end, value, unit, ref = row
            out.append((dataset, variant, {**dims, **flag}, measure, start, end, value, unit, ref))
        elif target == "obs":
            sid, start, end, _freq, value, _stage, ref = row
            s = series.get(sid, {})
            dims = {"series_id": sid, **(s.get("dimensions") or {}), **flag}
            out.append((s.get("dataset") or sid.split(".")[0].upper(), "ambiguous", dims, sid.split(".")[-2],
                        start, end, value, s.get("unit"), ref))  # fmt: skip
        else:  # cpi
            (
                base,
                series_name,
                state,
                sector,
                line,
                level,
                code,
                start,
                index,
                inflation,
                _i,
                status,
                ref,
            ) = row
            dims = {
                "state": state,
                "sector": sector,
                "line": line,
                "level": level,
                "code": code,
                "status": status,
            }
            for measure, value in (("index", index), ("inflation", inflation)):
                if value is not None:
                    out.append(("CPI", f"{base}/{series_name}", {**dims, **flag}, measure, start,
                                periods.month_end(start.year, start.month), value, None, ref))  # fmt: skip
    return out
