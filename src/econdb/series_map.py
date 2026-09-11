"""Which series each tracker-layout column shows (Phase 1: MoSPI, RBI-via-MoSPI and Yahoo sheets).

series_id grammar (docs/architecture.md): <family>.<base>.<geo>.<subject...>.<measure>.<freq>
Columns not listed here stay unmapped (their source is built in a later phase).
"""

import re
from dataclasses import dataclass, field

SOURCES = [
    {
        "source_id": "mospi",
        "name": "MoSPI e-Sankhyiki API (incl. RBI datasets)",
        "tier": "T1",
        "base_url": "https://esankhyiki.mospi.gov.in",
        "schedule": "0 19 * * *",
        "notes": "Package mospi-esankhyiki; 10 rows per page by default",
    },
    {
        "source_id": "yahoo",
        "name": "Yahoo Finance via yfinance (unofficial)",
        "tier": "T1b",
        "base_url": "https://finance.yahoo.com",
        "schedule": "30 18 * * 1-5",
        "notes": "Internal use only; never the sole source of a key series",
    },
    {
        "source_id": "datagovin",
        "name": "data.gov.in Open Government Data API",
        "tier": "T1b",
        "base_url": "https://api.data.gov.in",
        "schedule": "0 20 * * *",
        "notes": "Key DATAGOVIN_API_KEY; mandi resource returns the current day only",
    },
]

# Sheets whose every column must be mapped (tests), minus blocks from later-phase sources
IN_SCOPE = {
    *"A01 A02 A03 A04 A05 A06 A07 A08 A09 A10 A11 A12 A13 A14 A17 A18 A19 A20".split(),
    *"Q01 Q02 Q03 Q04 Q05 Q08 Q09 Q10 Q11 Q12".split(),
    *"M01 M02 M03 M04 M06 M08 M09 M11 M12 M13 M14 M15 M16 M17 M18 M19 M25 M26 M28".split(),
    *"W01 W02 D01 D02 D03 D04 O05 O07".split(),
}
LATER_BLOCKS = {("D02", "FBIL reference rate"), ("D03", "India")}


@dataclass
class Series:
    series_id: str
    source_id: str
    dataset: str | None
    unit: str
    agg_rule: str
    catalogue_id: str | None = None
    dimensions: dict = field(default_factory=dict)
    scale: str | None = None
    currency: str | None = None
    price_basis: str | None = None
    base_year: str | None = None
    period_basis: str | None = "FY"
    source_params: dict = field(default_factory=dict)
    derivation: dict | None = None
    notes: str | None = None


@dataclass
class Cell:
    series: Series
    agg: str | None = None  # series freq -> sheet freq
    transform: str | None = None  # 'yoy_pct' or 'stage'


def norm(text) -> str:
    return " ".join(str(text).split())


def slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", label.lower().replace(".", "")).strip("_")
    return s[:40].rstrip("_")


def _sid(*parts: str | None) -> str:
    return ".".join(p for p in parts if p)


def _b(base: str) -> str:
    return "b" + base.replace("-", "_")


# ---- family builders ------------------------------------------------------------------------


def cpi(base: str, geo: str, sector: str, item: str, measure: str = "index") -> Series:
    if base == "2024":
        cat = "02-005" if geo != "in" else "02-001" if item == "general" else "02-002"
    else:
        cat = {"2012": "02-006", "2010": "02-007"}[base]
    index = measure == "index"
    return Series(
        _sid("cpi", _b(base), geo, sector, item, measure, "m"),
        "mospi",
        "CPI",
        "index" if index else "percent",
        "mean" if index else "recompute",
        catalogue_id=cat,
        base_year=base,
        dimensions={"geo": geo, "sector": sector, "item": item},
        source_params={"base_year": base, "series": "Current"},
    )


WPI_CAT = {"2022-23": "02-012", "2011-12": "02-014", "2004-05": "02-015", "1993-94": "02-015"}


def wpi(base: str, item: str, measure: str = "index") -> Series:
    index = measure == "index"
    return Series(
        _sid("wpi", _b(base), "in", item, measure, "m"),
        "mospi",
        "WPI",
        "index" if index else "percent",
        "mean" if index else "recompute",
        catalogue_id=WPI_CAT[base],
        base_year=base,
        dimensions={"geo": "in", "item": item},
        source_params={"base_year": base},
    )


IIP_SECTORS = {"mining", "manufacturing", "electricity"}


def iip(base: str, item: str, freq: str = "m") -> Series:
    if item.startswith("mfg."):
        cat = "03-004"
    elif base == "2022-23":
        cat = "03-001" if item == "general" else "03-002" if item in IIP_SECTORS else "03-003"
    else:
        cat = "03-005" if base == "2011-12" else "03-006"
    return Series(
        _sid("iip", _b(base), "in", item, "index", freq),
        "mospi",
        "IIP",
        "index",
        "mean",
        catalogue_id=cat,
        base_year=base,
        dimensions={"geo": "in", "item": item},
        source_params={"base_year": base, "frequency": "Monthly" if freq == "m" else "Annually"},
    )


NAS_CAT = {
    "gdp": "01-001",
    "discrepancies": "01-001",
    "gva": "01-002",
    "gva_inst": "01-003",
    "pfce": "01-004",
    "gfce": "01-005",
    "gfcf": "01-006",
    "exports": "01-007",
    "imports": "01-007",
    "change_in_stocks": "01-008",
    "valuables": "01-008",
    "gni": "01-009",
    "nni": "01-009",
    "nni_per_capita": "01-010",
    "gds": "01-011",
    "gcf": "01-012",
}


def nas(base: str, subject: str, measure: str, freq: str) -> Series:
    money = measure in ("current", "constant")
    per_capita = subject == "nni_per_capita"
    return Series(
        _sid("nas", _b(base), "in", subject, measure, freq),
        "mospi",
        "NAS",
        "amount" if money else "percent",
        ("none" if per_capita else "sum") if money else "recompute",
        catalogue_id=NAS_CAT[subject.split(".")[0]],
        scale="crore" if money and not per_capita else None,
        currency="INR" if money else None,
        price_basis=measure if money else None,
        base_year=base,
        dimensions={"geo": "in", "subject": subject},
        source_params={"base_year": base, "frequency_code": 1 if freq == "a" else 2},
    )


PLFS_CAT = {"ur": "05-001", "lfpr": "05-002", "wpr": "05-003"}


def plfs(sector, gender, indicator, freq, approach=None, catalogue=None, unit="percent") -> Series:
    measure = f"{indicator}_{approach}" if approach else indicator
    return Series(
        _sid("plfs", "in", sector, gender, measure, freq),
        "mospi",
        "PLFS",
        unit,
        "none",
        catalogue_id=catalogue or PLFS_CAT[indicator],
        period_basis="AY" if freq == "a" else "FY",
        dimensions={"geo": "in", "sector": sector, "gender": gender, "indicator": indicator},
        source_params={"frequency_code": {"a": 1, "q": 2, "m": 3}[freq]},
        notes="Annual: July-June years to 2023-24, calendar year from 2025"
        if freq == "a"
        else None,
    )


def simple(family, dataset, subject, measure, freq, unit, agg, cat, **kw) -> Series:
    return Series(
        _sid(family, "in", subject, measure, freq),
        "mospi",
        dataset,
        unit,
        agg,
        catalogue_id=cat,
        dimensions={"geo": "in", "subject": subject},
        **kw,
    )


def linked(series_id, dataset, base, inputs, factor_family, dims) -> Series:
    """Series computed from older bases with official linking factors (meta.linking_factor)."""
    return Series(
        series_id,
        "mospi",
        dataset,
        "index",
        "mean",
        catalogue_id="17-002",
        base_year=base,
        dimensions=dims,
        derivation={"method": "link", "linking_factor_family": factor_family, "inputs": inputs},
    )


# ---- label tables ---------------------------------------------------------------------------

STATES = {
    "All India": "in",
    "Andhra Pradesh": "in_ap",
    "Arunachal Pradesh": "in_ar",
    "Assam": "in_as",
    "Bihar": "in_br",
    "Chhattisgarh": "in_cg",
    "Goa": "in_ga",
    "Gujarat": "in_gj",
    "Haryana": "in_hr",
    "Himachal Pradesh": "in_hp",
    "Jharkhand": "in_jh",
    "Karnataka": "in_ka",
    "Kerala": "in_kl",
    "Madhya Pradesh": "in_mp",
    "Maharashtra": "in_mh",
    "Manipur": "in_mn",
    "Meghalaya": "in_ml",
    "Mizoram": "in_mz",
    "Nagaland": "in_nl",
    "Odisha": "in_od",
    "Punjab": "in_pb",
    "Rajasthan": "in_rj",
    "Sikkim": "in_sk",
    "Tamil Nadu": "in_tn",
    "Telangana": "in_ts",
    "Tripura": "in_tr",
    "Uttar Pradesh": "in_up",
    "Uttarakhand": "in_uk",
    "West Bengal": "in_wb",
    "Andaman & Nicobar Islands": "in_an",
    "Chandigarh": "in_ch",
    "Dadra & Nagar Haveli and Daman & Diu": "in_dh",
    "Delhi": "in_dl",
    "Jammu & Kashmir": "in_jk",
    "Ladakh": "in_la",
    "Lakshadweep": "in_ld",
    "Puducherry": "in_py",
}

GVA_ANNUAL = {
    "Agriculture, Livestock, Forestry and Fishing": "agri",
    "Mining and Quarrying": "mining",
    "Manufacturing": "manufacturing",
    "Electricity, Gas, Water Supply & Other Utility Services": "utilities",
    "Construction": "construction",
    "Trade, Hotels, Transport, Communication & Services Related to Broadcasting": "trade_hotels",
    "Financial, Real Estate & Professional Services": "finance_realestate",
    "Public Administration, Defence & Other Services": "public_admin",
    "Total Gross Value Added": "total",
}
GVA_QUARTERLY = {
    "Agriculture, livestock, forestry & fishing": "agri",
    "Mining & quarrying": "mining",
    "Manufacturing": "manufacturing",
    "Electricity, gas, water & utilities": "utilities",
    "Construction": "construction",
    "Trade, hotels, transport, communication": "trade_hotels",
    "Financial, real estate & professional": "finance_realestate",
    "Public admin, defence & other services": "public_admin",
    "Total GVA": "total",
}

CPI_DIVISIONS = {
    "2024": {
        "CPI (General)": "general",
        "Food and beverages": "food_beverages",
        "Paan, tobacco and intoxicants": "paan_tobacco",
        "Clothing and footwear": "clothing_footwear",
        "Housing, water, electricity, gas and other fuels": "housing_utilities",
        "Furnishings, household equipment and maintenance": "furnishings",
        "Health": "health",
        "Transport": "transport",
        "Information and communication": "info_communication",
        "Recreation, sport and culture": "recreation",
        "Education services": "education",
        "Restaurants and accommodation services": "restaurants_accommodation",
        "Personal care, social protection and misc.": "personal_care_misc",
    },
    "2012": {
        "CPI (General)": "general",
        "Food and beverages": "food_beverages",
        "Pan, tobacco and intoxicants": "paan_tobacco",
        "Clothing and footwear": "clothing_footwear",
        "Housing": "housing",
        "Fuel and light": "fuel_light",
        "Miscellaneous": "miscellaneous",
        "Consumer Food Price Index (CFPI)": "cfpi",
    },
}

IIP_ITEMS = {
    "General": "general",
    "Mining": "mining",
    "Manufacturing": "manufacturing",
    "Electricity": "electricity",
    "Primary goods": "primary_goods",
    "Basic goods": "basic_goods",
    "Capital goods": "capital_goods",
    "Intermediate goods": "intermediate_goods",
    "Infrastructure/construction goods": "infra_construction_goods",
    "Consumer durables": "consumer_durables",
    "Consumer non-durables": "consumer_nondurables",
}
IIP_USE_2011 = [
    "Primary goods",
    "Capital goods",
    "Intermediate goods",
    "Infrastructure/construction goods",
    "Consumer durables",
    "Consumer non-durables",
]
IIP_USE_2004 = [
    "Basic goods",
    "Capital goods",
    "Intermediate goods",
    "Consumer durables",
    "Consumer non-durables",
]
IIP_USE_BASED = {"2022-23": IIP_USE_2011, "2011-12": IIP_USE_2011, "2004-05": IIP_USE_2004}
NIC_2DIGIT = [
    "Food products",
    "Beverages",
    "Tobacco products",
    "Textiles",
    "Wearing apparel",
    "Leather products",
    "Wood products",
    "Paper products",
    "Printing & recorded media",
    "Coke & refined petroleum",
    "Chemicals",
    "Pharmaceuticals",
    "Rubber & plastics",
    "Other non-metallic minerals",
    "Basic metals",
    "Fabricated metal products",
    "Computer, electronic & optical",
    "Electrical equipment",
    "Machinery & equipment n.e.c.",
    "Motor vehicles & trailers",
    "Other transport equipment",
    "Furniture",
    "Other manufacturing",
]
WPI_ITEMS = {
    "All commodities": "all_commodities",
    "Primary articles": "primary_articles",
    "Fuel & power": "fuel_power",
    "Manufactured products": "manufactured_products",
    "WPI Food Index": "food_index",
}
FX_RESERVES = [
    ("Total", "total"),
    ("Foreign currency assets", "fca"),
    ("Gold", "gold"),
    ("SDR", "sdr"),
    ("Reserve tranche (IMF)", "rtp"),
]
PARTNERS = {
    "USA": "us",
    "China": "cn",
    "UAE": "ae",
    "Netherlands": "nl",
    "UK": "gb",
    "Singapore": "sg",
    "Bangladesh": "bd",
    "Germany": "de",
    "Saudi Arabia": "sa",
    "Hong Kong": "hk",
    "Russia": "ru",
    "Iraq": "iq",
    "Indonesia": "id",
    "Switzerland": "ch",
    "Korea": "kr",
}

# layout label: (catalogue YAHOO_TICKERS name, series_id stem, unit, catalogue_id)
YAHOO = {
    "Nifty 50": ("Nifty 50", "eq.in.nifty50", "index points", "07-001"),
    "Sensex": ("Sensex", "eq.in.sensex", "index points", "07-001"),
    "Nifty Bank": ("Nifty Bank", "eq.in.nifty_bank", "index points", "07-002"),
    "Nifty IT": ("Nifty IT", "eq.in.nifty_it", "index points", "07-002"),
    "Nifty Auto": ("Nifty Auto", "eq.in.nifty_auto", "index points", "07-002"),
    "Nifty FMCG": ("Nifty FMCG", "eq.in.nifty_fmcg", "index points", "07-002"),
    "Nifty Pharma": ("Nifty Pharma", "eq.in.nifty_pharma", "index points", "07-002"),
    "Nifty Metal": ("Nifty Metal", "eq.in.nifty_metal", "index points", "07-002"),
    "Nifty Realty": ("Nifty Realty", "eq.in.nifty_realty", "index points", "07-002"),
    "Nifty Energy": ("Nifty Energy", "eq.in.nifty_energy", "index points", "07-002"),
    "Nifty PSU Bank": ("Nifty PSU Bank", "eq.in.nifty_psu_bank", "index points", "07-002"),
    "Nifty Infra": ("Nifty Infra", "eq.in.nifty_infra", "index points", "07-002"),
    "Nifty Media": ("Nifty Media", "eq.in.nifty_media", "index points", "07-002"),
    "Nifty Midcap 50": ("Nifty Midcap 50", "eq.in.nifty_midcap50", "index points", "07-003"),
    "Nifty 500": ("Nifty 500", "eq.in.nifty500", "index points", "07-003"),
    "India VIX": ("India VIX", "eq.in.india_vix", "index points", "07-004"),
    "USD/INR": ("USD/INR", "fx.in.usdinr", "₹ per USD", "07-011"),
    "EUR/INR": ("EUR/INR", "fx.in.eurinr", "₹ per EUR", "07-012"),
    "GBP/INR": ("GBP/INR", "fx.in.gbpinr", "₹ per GBP", "07-012"),
    "JPY/INR": ("JPY/INR", "fx.in.jpyinr", "₹ per JPY", "07-012"),
    "AED/INR": ("AED/INR", "fx.in.aedinr", "₹ per AED", "07-012"),
    "US Dollar Index": ("US Dollar Index", "fx.us.dxy", "index points", "16-007"),
    "Gold (US$/oz)": ("Gold", "cmdty.world.gold", "US$ per oz", "07-019"),
    "Silver (US$/oz)": ("Silver", "cmdty.world.silver", "US$ per oz", "07-019"),
    "Brent (US$/bbl)": ("Brent crude", "cmdty.world.brent", "US$ per bbl", "07-019"),
    "WTI (US$/bbl)": ("WTI crude", "cmdty.world.wti", "US$ per bbl", "07-019"),
    "Natural gas (US$/mmBtu)": (
        "Natural gas",
        "cmdty.world.natural_gas",
        "US$ per mmBtu",
        "07-019",
    ),
    "Copper (US$/lb)": ("Copper", "cmdty.world.copper", "US$ per lb", "07-019"),
    "S&P 500": ("S&P 500", "eq.us.sp500", "index points", "16-008"),
    "Nasdaq": ("Nasdaq", "eq.us.nasdaq", "index points", "16-008"),
    "Dow Jones": ("Dow Jones", "eq.us.dow_jones", "index points", "16-008"),
    "Nikkei 225": ("Nikkei 225", "eq.jp.nikkei225", "index points", "16-008"),
    "Hang Seng": ("Hang Seng", "eq.hk.hang_seng", "index points", "16-008"),
    "FTSE 100": ("FTSE 100", "eq.gb.ftse100", "index points", "16-008"),
    "US 10Y yield (%)": ("US 10Y yield", "yield.us.10y", "percent", "16-006"),
    "US VIX": ("US VIX", "eq.us.vix", "index points", "16-008"),
}
INDIA_MARKETS = list(YAHOO)[:16]  # D01 / W01 / M25 columns, in layout order
FX_YAHOO = ["USD/INR", "EUR/INR", "GBP/INR", "JPY/INR", "AED/INR"]
COMMODITIES = ["Gold (US$/oz)", "Silver (US$/oz)", "Brent (US$/bbl)", "WTI (US$/bbl)"]
COMMODITIES += ["Natural gas (US$/mmBtu)", "Copper (US$/lb)"]
GLOBAL_INDICES = ["S&P 500", "Nasdaq", "Dow Jones", "Nikkei 225", "Hang Seng", "FTSE 100"]
# M26 / W02 column order
GLOBAL_MARKETS = FX_YAHOO + COMMODITIES + ["US Dollar Index", "US 10Y yield (%)", "US VIX"]
GLOBAL_MARKETS += GLOBAL_INDICES
MARKETS_END = ["Nifty 50", "Sensex", "India VIX", "USD/INR", "Brent (US$/bbl)", "Gold (US$/oz)"]
MARKETS_AVG = ["Nifty 50", "Sensex", "USD/INR", "Brent (US$/bbl)"]


def build(tickers: dict[str, str], rbi_codes: dict[int, tuple]) -> dict[tuple[str, str, str], Cell]:
    """Map (sheet_code, block title, column label) -> Cell.

    tickers: catalogue YAHOO_TICKERS name -> ticker (working ones only).
    rbi_codes: catalogue RBI_API_39 code -> (indicator, currency, frequency).
    """
    cells: dict[tuple[str, str, str], Cell] = {}

    def put(sheet, block, label, series, agg=None, transform=None):
        key = (sheet, norm(block), norm(label))
        if key in cells:
            raise ValueError(f"mapped twice: {key}")
        cells[key] = Cell(series, agg, transform)

    def rbi(code, family, subject, measure, freq, cat, money=None, unit=None, agg="sum") -> Series:
        _, currency, frequency = rbi_codes[code]
        if frequency[0] != freq.upper():
            raise ValueError(f"RBI code {code} is {frequency}, not {freq}")
        iso = {"usd": "USD", "inr": "INR"}.get(money or "")
        if iso and currency and {"US$": "USD", "₹": "INR"}[currency] != iso:
            raise ValueError(f"RBI code {code} is in {currency}, not {iso}")
        return Series(
            _sid(family, "in", subject, measure, freq),
            "mospi",
            "RBI",
            "amount" if money else unit,
            agg,
            catalogue_id=cat,
            scale={"usd": "million", "inr": "crore"}.get(money or ""),
            currency=iso,
            dimensions={"geo": "in", "subject": subject},
            source_params={"indicator_code": code},
        )

    def yahoo(label) -> Series:
        name, stem, unit, cat = YAHOO[label]
        return Series(
            stem + ".close.d",
            "yahoo",
            "yfinance",
            unit,
            "end_mean",
            catalogue_id=cat,
            dimensions={"geo": stem.split(".")[1]},
            source_params={"ticker": tickers[name], "field": "Close"},
        )

    def trade_m(subject, money) -> Series:  # M13 and Q11
        oil = "oil" in subject
        code = {("usd", False): 12, ("inr", False): 13, ("usd", True): 42, ("inr", True): 24}
        return rbi(
            code[(money, oil)], "trade", subject, money, "m", "08-002" if oil else "08-001", money
        )

    bases = ["2022-23", "2011-12", "2004-05", "1993-94"]  # WPI and IIP, newest first
    cpi_linked = linked(
        "cpi.l2024.in.combined.general.index.m",
        "CPI",
        "2024",
        [cpi(b, "in", "combined", "general").series_id for b in ("2012", "2024")],
        "CPI (All-India)",
        {"geo": "in", "sector": "combined", "item": "general"},
    )
    wpi_linked = linked(
        "wpi.l2022_23.in.all_commodities.index.m",
        "WPI",
        "2022-23",
        [wpi(b, "all_commodities").series_id for b in reversed(bases)],
        "WPI",
        {"geo": "in", "item": "all_commodities"},
    )
    iip_linked = linked(
        "iip.l2022_23.in.general.index.m",
        "IIP",
        "2022-23",
        [iip(b, "general").series_id for b in reversed(bases)],
        "IIP",
        {"geo": "in", "item": "general"},
    )

    # ---- Annual ----------------------------------------------------------------------------
    for base in ("2022-23", "2011-12"):
        blk = f"Base {base}"
        for label, subject, measure in [
            ("GDP (current)", "gdp", "current"),
            ("GDP (constant)", "gdp", "constant"),
            ("GNI (current)", "gni", "current"),
            ("NNI (current)", "nni", "current"),
            ("Per capita NNI (₹, current)", "nni_per_capita", "current"),
            ("PFCE (current)", "pfce", "current"),
            ("GFCE (current)", "gfce", "current"),
            ("GFCF (current)", "gfcf", "current"),
            ("Gross domestic saving % GDP", "gds", "pct_gdp"),
            ("Gross capital formation % GDP", "gcf", "pct_gdp"),
        ]:
            put("A01", blk, label, nas(base, subject, measure, "a"))
        put("A01", "Estimate stage", blk, nas(base, "gdp", "current", "a"), transform="stage")

        for basis in ("current", "constant"):
            for label, ind in GVA_ANNUAL.items():
                put("A02", f"{blk} – {basis} prices", label, nas(base, f"gva.{ind}", basis, "a"))

        for label, subject in [
            ("Public Non-Financial Corporations", "gva_inst.public_nfc"),
            ("Private Non-Financial Corporations", "gva_inst.private_nfc"),
            ("Public Financial Corporations", "gva_inst.public_fc"),
            ("Private Financial Corporations", "gva_inst.private_fc"),
            ("General Government", "gva_inst.general_govt"),
            ("Households Including NPISH", "gva_inst.households"),
            ("Total Gross Value Added", "gva.total"),
        ]:
            put("A03", f"{blk} – current prices", label, nas(base, subject, "current", "a"))

        for label, subject, measure in [
            ("Gross domestic saving", "gds", "current"),
            ("Household saving", "gds.household", "current"),
            ("Private corporate saving", "gds.private_corporate", "current"),
            ("Public saving", "gds.public", "current"),
            ("GDS % GDP", "gds", "pct_gdp"),
            ("Gross capital formation", "gcf", "current"),
            ("GCF % GDP", "gcf", "pct_gdp"),
        ]:
            put("A04", blk, label, nas(base, subject, measure, "a"))
    put(
        "A02",
        "Base 2022-23 – estimate stage",
        "Estimate stage",
        nas("2022-23", "gva.total", "current", "a"),
        transform="stage",
    )

    for label, subject in [
        ("Current account balance", "current_account"),
        ("Trade balance", "trade_balance"),
        ("Invisibles (net)", "invisibles_net"),
        ("Capital account (net)", "capital_account_net"),
        ("FDI (net)", "fdi_net"),
        ("FPI (net)", "fpi_net"),
        ("Overall balance", "overall_balance"),
    ]:
        cat = "08-008" if subject == "invisibles_net" else "08-007"
        put("A05", "Key components", label, rbi(8, "bop", subject, "usd", "a", cat, "usd"))
    cad = rbi(22, "bop", "cad", "pct_gdp", "a", "08-007", unit="percent", agg="recompute")
    put("A05", "Key components", "CAD % GDP", cad)

    for blk, money, code in (("US$ million", "usd", 16), ("₹ crore", "inr", 17)):
        for label, subject in (
            ("Exports", "exports"),
            ("Imports", "imports"),
            ("Trade balance", "balance"),
        ):
            put("A06", blk, label, rbi(code, "trade", subject, money, "a", "08-001", money))

    commodities = {
        ("Exports", "exports", 44): [
            "Petroleum products",
            "Engineering goods",
            "Gems & jewellery",
            "Drugs & pharmaceuticals",
            "Electronic goods",
            "Organic & inorganic chemicals",
            "Textiles & apparel",
            "Agricultural products",
        ],
        ("Imports", "imports", 46): [
            "Crude & petroleum",
            "Gold",
            "Electronic goods",
            "Coal & coke",
            "Machinery",
            "Chemicals",
            "Vegetable oils",
            "Pearls & precious stones",
        ],
    }
    for (blk, flow, code), labels in commodities.items():
        for label in labels:
            subject = f"{flow}.{slug(label)}"
            put("A07", blk, label, rbi(code, "trade", subject, "usd", "a", "08-003", "usd"))

    exports_to = ["USA", "China", "UAE", "Netherlands", "UK"]
    exports_to += ["Singapore", "Bangladesh", "Germany", "Saudi Arabia", "Hong Kong"]
    imports_from = ["China", "Russia", "UAE", "USA", "Saudi Arabia"]
    imports_from += ["Iraq", "Indonesia", "Singapore", "Switzerland", "Korea"]
    for blk, prefix, countries in (
        ("Exports to", "exports.to_", exports_to),
        ("Imports from", "imports.from_", imports_from),
    ):
        for country in countries:
            subject = prefix + PARTNERS[country]
            put("A08", blk, country, rbi(11, "trade", subject, "usd", "a", "08-004", "usd"))

    for label, subject in [
        ("Total", "total"),
        ("Long-term", "long_term"),
        ("Short-term", "short_term"),
        ("Commercial borrowings", "commercial_borrowings"),
        ("NRI deposits", "nri_deposits"),
        ("Multilateral", "multilateral"),
        ("Bilateral", "bilateral"),
    ]:
        put(
            "A09",
            "Stock",
            label,
            rbi(25, "extdebt", subject, "usd", "a", "08-011", "usd", agg="end"),
        )
    for label, subject, measure in (
        ("Debt % GDP", "total", "pct_gdp"),
        ("Short-term % of reserves", "short_term", "pct_reserves"),
    ):
        ratio = rbi(25, "extdebt", subject, measure, "a", "08-011", unit="percent", agg="recompute")
        put("A09", "Ratios", label, ratio)

    for label, subject in FX_RESERVES:
        put(
            "A10",
            "US$ million",
            label,
            rbi(48, "fxres", subject, "usd", "a", "08-012", "usd", agg="end"),
        )
    cover = rbi(48, "fxres", "import_cover", "months", "a", "08-012", unit="months", agg="none")
    put("A10", "US$ million", "Import cover (months)", cover)

    for label in ("USD", "GBP", "EUR", "JPY", "SDR"):
        unit = f"₹ per {label}"
        for blk, measure, agg in (("Annual average", "avg", "mean"), ("End-year", "eop", "end")):
            rate = rbi(31, "fxrate", label.lower(), measure, "a", "08-015", unit=unit, agg=agg)
            put("A11", blk, label, rate)

    for ind in ("UR", "LFPR", "WPR"):
        for lab, sector, gender in (
            ("Total", "total", "persons"),
            ("Rural", "rural", "persons"),
            ("Urban", "urban", "persons"),
            ("Male", "total", "male"),
            ("Female", "total", "female"),
        ):
            put("A12", "Rates", f"{ind} – {lab}", plfs(sector, gender, ind.lower(), "a", "us"))
    plfs_other = {
        ("Workers by status", "05-004"): [
            ("Self-employed %", "self_employed_pct", "percent"),
            ("Regular wage/salaried %", "regular_wage_pct", "percent"),
            ("Casual labour %", "casual_pct", "percent"),
        ],
        ("Earnings", "05-006"): [
            ("Regular wage/salary (₹/month)", "earn_regular", "₹ per month"),
            ("Casual wage (₹/day)", "earn_casual", "₹ per day"),
            ("Self-employment earnings (₹/30 days)", "earn_self", "₹ per 30 days"),
        ],
        ("Job quality (regular employees)", "05-005"): [
            ("No written contract %", "no_contract_pct", "percent"),
            ("Not eligible for paid leave %", "no_paid_leave_pct", "percent"),
            ("No social security %", "no_social_security_pct", "percent"),
        ],
    }
    for (blk, cat), items in plfs_other.items():
        for label, measure, unit in items:
            put("A12", blk, label, plfs("total", "persons", measure, "a", catalogue=cat, unit=unit))

    for label, subject, kind in [
        ("Factories", "factories", "count"),
        ("Fixed capital", "fixed_capital", "inr"),
        ("Invested capital", "invested_capital", "inr"),
        ("Workers", "workers", "count"),
        ("Total persons engaged", "persons_engaged", "count"),
        ("Wages to workers", "wages_workers", "inr"),
        ("Total output", "output", "inr"),
        ("Total input", "input", "inr"),
        ("GVA", "gva", "inr"),
        ("Profits", "profits", "inr"),
    ]:
        money = kind == "inr"
        asi = simple(
            "asi",
            "ASI",
            subject,
            kind,
            "a",
            "amount" if money else "number",
            "none",
            "03-009",
            scale="lakh" if money else None,
            currency="INR" if money else None,
            notes="NIC-2004 classification to 2007-08, NIC-2008 from 2008-09",
        )
        put("A13", "All industries", label, asi)

    energy = {
        ("Primary supply", "supply", 1): [
            ("Total", "total"),
            ("Coal", "coal"),
            ("Crude oil & products", "oil"),
            ("Natural gas", "natural_gas"),
            ("Nuclear", "nuclear"),
            ("Hydro", "hydro"),
            ("Renewables", "renewables"),
        ],
        ("Final consumption", "consumption", 2): [
            ("Total", "total"),
            ("Industry", "industry"),
            ("Transport", "transport"),
            ("Residential", "residential"),
            ("Commercial & public", "commercial_public"),
            ("Agriculture", "agriculture"),
        ],
    }
    for (blk, flow, code), items in energy.items():
        for label, item in items:
            params = {"use_of_energy_balance_code": code}
            balance = simple(
                "energy",
                "ENERGY",
                f"{flow}.{item}",
                "ktoe",
                "a",
                "KToE",
                "none",
                "11-009",
                source_params=params,
            )
            put("A14", blk, label, balance)

    for base in bases:
        for label in ("General", "Mining", "Manufacturing", "Electricity"):
            put("A17", f"Base {base}", label, iip(base, IIP_ITEMS[label], "a"))

    for base in ("2024", "2012"):
        general = cpi(base, "in", "combined", "general")
        put("A18", f"Base {base}=100", "Index – Combined (FY avg)", general, agg="mean")
        put("A18", f"Base {base}=100", "Inflation %", general, agg="mean", transform="yoy_pct")
    put("A18", "Linked (2024=100)", "Index – Combined", cpi_linked, agg="mean")
    put("A18", "Linked (2024=100)", "Inflation %", cpi_linked, agg="mean", transform="yoy_pct")

    for base in bases:
        all_commodities = wpi(base, "all_commodities")
        put("A19", f"Base {base}", "All commodities (FY avg)", all_commodities, agg="mean")
        put("A19", f"Base {base}", "Inflation %", all_commodities, agg="mean", transform="yoy_pct")

    for label in MARKETS_END:
        put("A20", "FY-end close", label, yahoo(label), agg="end")
        put("Q12", "Quarter-end close", label, yahoo(label), agg="end")
    for label in MARKETS_AVG:
        put("A20", "FY average", label, yahoo(label), agg="mean")
        put("Q12", "Quarterly average", label, yahoo(label), agg="mean")

    # ---- Quarterly -------------------------------------------------------------------------
    expenditure = [
        ("GDP", "gdp"),
        ("PFCE", "pfce"),
        ("GFCE", "gfce"),
        ("GFCF", "gfcf"),
        ("Change in stocks", "change_in_stocks"),
        ("Valuables", "valuables"),
        ("Exports of G&S", "exports"),
        ("Imports of G&S", "imports"),
        ("Discrepancies", "discrepancies"),
    ]
    for base in ("2022-23", "2011-12"):
        for basis in ("constant", "current"):
            for label, subject in expenditure:
                put("Q01", f"Base {base} – {basis} prices", label, nas(base, subject, basis, "q"))
        gdp = nas(base, "gdp", "constant", "q")
        put("Q01", "Real GDP growth % YoY", f"Base {base}", gdp, transform="yoy_pct")
        put("Q01", "Estimate stage", f"Base {base}", gdp, transform="stage")
        for label, ind in GVA_QUARTERLY.items():
            gva = nas(base, f"gva.{ind}", "constant", "q")
            put("Q02", f"Base {base} – constant prices", label, gva)
            if base == "2022-23":
                put("Q02", "Real GVA growth % YoY – Base 2022-23", label, gva, transform="yoy_pct")

    bop_quarterly = {
        "Current account": [
            ("Current account balance", "current_account"),
            ("Merchandise trade balance", "trade_balance"),
            ("Services (net)", "services_net"),
            ("Primary income (net)", "primary_income_net"),
            ("Transfers / remittances (net)", "transfers_net"),
        ],
        "Capital & financial account": [
            ("Capital account (net)", "capital_account_net"),
            ("FDI (net)", "fdi_net"),
            ("FPI (net)", "fpi_net"),
            ("Loans incl. ECB (net)", "loans_net"),
            ("Banking capital (net)", "banking_capital_net"),
            ("Errors & omissions", "errors_omissions"),
        ],
        "Overall": [
            ("Overall balance", "overall_balance"),
            ("Change in reserves (− = increase)", "reserves_change"),
        ],
    }
    for blk, items in bop_quarterly.items():
        for label, subject in items:
            put("Q03", blk, label, rbi(4, "bop", subject, "usd", "q", "08-007", "usd"))
    cad = rbi(4, "bop", "cad", "pct_gdp", "q", "08-007", unit="percent", agg="recompute")
    put("Q03", "Overall", "CAD % of GDP", cad)

    for label, subject in [
        ("Total", "total"),
        ("Long-term", "long_term"),
        ("Short-term", "short_term"),
        ("Sovereign", "sovereign"),
        ("Non-sovereign", "non_sovereign"),
    ]:
        debt = rbi(27, "extdebt", subject, "usd", "q", "08-011", "usd", agg="end")
        put("Q04", "External debt", label, debt)
    ratio = rbi(27, "extdebt", "total", "pct_gdp", "q", "08-011", unit="percent", agg="recompute")
    put("Q04", "External debt", "Debt % of GDP", ratio)

    for blk, sector in (("Urban (since 2018)", "urban"), ("Rural + Urban (from 2025)", "total")):
        for ind in ("UR", "LFPR", "WPR"):
            for lab, gender in (("Total", "persons"), ("Male", "male"), ("Female", "female")):
                put("Q05", blk, f"{ind} – {lab}", plfs(sector, gender, ind.lower(), "q", "cws"))

    for base in ("2024", "2012"):
        general = cpi(base, "in", "combined", "general")
        put("Q08", f"Base {base}=100", "Index – Combined (avg)", general, agg="mean")
        put(
            "Q08",
            f"Base {base}=100",
            "Inflation % – Combined",
            general,
            agg="mean",
            transform="yoy_pct",
        )
    cpi_2010 = cpi("2010", "in", "combined", "general")
    put("Q08", "Base 2010=100", "Index – Combined (avg)", cpi_2010, agg="mean")
    put("Q08", "Linked (2024=100)", "Index – Combined", cpi_linked, agg="mean")
    put("Q08", "Linked (2024=100)", "Inflation %", cpi_linked, agg="mean", transform="yoy_pct")

    for base in bases:
        all_commodities = wpi(base, "all_commodities")
        put("Q09", f"Base {base}", "All commodities (avg)", all_commodities, agg="mean")
        put("Q09", f"Base {base}", "Inflation %", all_commodities, agg="mean", transform="yoy_pct")
        general = iip(base, "general")
        put("Q10", f"Base {base}", "General (avg)", general, agg="mean")
        put("Q10", f"Base {base}", "Growth % YoY", general, agg="mean", transform="yoy_pct")
        if base in ("2022-23", "2011-12"):
            put(
                "Q10", f"Base {base}", "Manufacturing (avg)", iip(base, "manufacturing"), agg="mean"
            )

    for label, subject in (
        ("Exports", "exports"),
        ("Imports", "imports"),
        ("Trade balance", "balance"),
        ("Oil imports", "imports.oil"),
        ("Non-oil exports", "exports.non_oil"),
    ):
        put("Q11", "US$ million", label, trade_m(subject, "usd"), agg="sum")

    # ---- Monthly ---------------------------------------------------------------------------
    for base, blk in (("2024", "Base 2024=100"), ("2012", "Base 2012=100 (2011→2025)")):
        for sector in ("rural", "urban", "combined"):
            put("M01", blk, f"Index – {sector.title()}", cpi(base, "in", sector, "general"))
            infl = cpi(base, "in", sector, "general", "infl_yoy")
            put("M01", blk, f"Inflation % – {sector.title()}", infl)
    for sector in ("rural", "urban", "combined"):
        old = cpi("2010", "in", sector, "general")
        put("M01", "Base 2010=100 (2011→2014)", f"Index – {sector.title()}", old)
    blk = "Linked series (2024=100, official linking factor)"
    put("M01", blk, "Index – Combined (linked)", cpi_linked)
    put("M01", blk, "Inflation % – Combined (linked)", cpi_linked, transform="yoy_pct")

    for base, divisions in CPI_DIVISIONS.items():
        for label, item in divisions.items():
            put("M02", f"Base {base}=100 – index", label, cpi(base, "in", "combined", item))
            infl = cpi(base, "in", "combined", item, "infl_yoy")
            put("M02", f"Base {base}=100 – inflation %", label, infl)

    for base in ("2024", "2012"):
        for label, geo in STATES.items():
            put("M03", f"Base {base}=100", label, cpi(base, geo, "combined", "general"))

    for base in ("2019", "1986-87"):
        for label, family, item in (
            ("CPI-AL General", "cpi_al", "general"),
            ("CPI-RL General", "cpi_rl", "general"),
            ("CPI-AL Food", "cpi_al", "food"),
            ("CPI-RL Food", "cpi_rl", "food"),
        ):
            labourers = Series(
                _sid(family, _b(base), "in", item, "index", "m"),
                "mospi",
                "CPIALRL",
                "index",
                "mean",
                catalogue_id="02-010",
                base_year=base,
                dimensions={"geo": "in", "item": item},
                source_params={"base_year": base},
            )
            put("M04", f"Base {base}=100", label, labourers)

    wpi_coverage = {"2022-23": "2023→2026", "2011-12": "2012→2026", "2004-05": "2005→2017"}
    wpi_coverage["1993-94"] = "1994→2010"
    for base in bases:
        blk = f"Base {base}=100 ({wpi_coverage[base]})"
        for label, item in WPI_ITEMS.items():
            if item != "food_index" or base in ("2022-23", "2011-12"):
                put("M06", blk, label, wpi(base, item))
        put("M06", blk, "Inflation – all commodities (%)", wpi(base, "all_commodities", "infl_yoy"))
    put("M06", "Linked series (2022-23=100)", "All commodities (linked)", wpi_linked)
    put(
        "M06",
        "Linked series (2022-23=100)",
        "Inflation % (linked)",
        wpi_linked,
        transform="yoy_pct",
    )

    iip_coverage = {**wpi_coverage, "1993-94": "1994→2011"}
    for base in bases:
        for label in ["General", "Mining", "Manufacturing", "Electricity"] + IIP_USE_BASED.get(
            base, []
        ):
            put(
                "M08", f"Base {base}=100 ({iip_coverage[base]})", label, iip(base, IIP_ITEMS[label])
            )
    put("M08", "Linked series (2022-23=100)", "General (linked)", iip_linked)
    put(
        "M08",
        "Linked series (2022-23=100)",
        "Growth % YoY (linked)",
        iip_linked,
        transform="yoy_pct",
    )

    for base in ("2022-23", "2011-12"):
        for label in NIC_2DIGIT:
            put("M09", f"Base {base}=100", label, iip(base, f"mfg.{slug(label)}"))

    isp = simple(
        "isp",
        "ISP",
        "overall",
        "index",
        "m",
        "index",
        "mean",
        "03-008",
        source_params={"frequency_code": 2},
        notes="Trial series; base year to confirm",
    )
    put("M11", "Trial series", "ISP – overall", isp)
    put("M11", "Trial series", "Growth % YoY", isp, transform="yoy_pct")

    for blk, ind in (("Unemployment rate", "ur"), ("LFPR", "lfpr"), ("WPR", "wpr")):
        for label, sector, gender in (
            ("Rural", "rural", "persons"),
            ("Urban", "urban", "persons"),
            ("Total", "total", "persons"),
            ("Male", "total", "male"),
            ("Female", "total", "female"),
        ):
            put("M12", blk, label, plfs(sector, gender, ind, "m", "cws"))

    for blk, money in (("US$ million", "usd"), ("₹ crore", "inr")):
        for label, subject in (
            ("Exports", "exports"),
            ("Imports", "imports"),
            ("Trade balance", "balance"),
            ("Oil exports", "exports.oil"),
            ("Non-oil exports", "exports.non_oil"),
            ("Oil imports", "imports.oil"),
            ("Non-oil imports", "imports.non_oil"),
        ):
            put("M13", blk, label, trade_m(subject, money))
        for label, subject in FX_RESERVES:
            put(
                "M14", blk, label, rbi(47, "fxres", subject, money, "m", "08-012", money, agg="end")
            )

    for label in ("USD", "GBP", "EUR", "JPY", "SDR"):
        unit = "₹ per 100 JPY" if label == "JPY" else f"₹ per {label}"
        avg_code = 33 if label == "SDR" else 36
        avg = rbi(avg_code, "fxrate", label.lower(), "avg", "m", "08-015", unit=unit, agg="mean")
        put("M15", "Monthly average", label, avg)
        eop = rbi(33, "fxrate", label.lower(), "eop", "m", "08-015", unit=unit, agg="end")
        put("M15", "End-month", label, eop)
    for label in ("High", "Low"):
        extreme = rbi(
            29, "fxrate", "usd", label.lower(), "m", "08-015", unit="₹ per USD", agg="none"
        )
        put("M15", "USD month high / low", label, extreme)

    for label, subject in (("Purchase", "purchase"), ("Sale", "sale"), ("Net", "net")):
        put("M16", "Spot market", label, rbi(28, "fx_ops", subject, "usd", "m", "08-013", "usd"))
    put(
        "M16",
        "Rupee equivalent",
        "Net (₹ crore)",
        rbi(28, "fx_ops", "net", "inr", "m", "08-013", "inr"),
    )

    for label in ("1-month", "3-month", "6-month"):
        subject = f"usd_{label[0]}m"
        premia = rbi(
            34, "fwd_premia", subject, "rate", "m", "08-014", unit="% per annum", agg="mean"
        )
        put("M17", "Monthly average", label, premia)

    for label, subject in (
        ("FCNR(B)", "fcnr_b"),
        ("NRE", "nre"),
        ("NRO", "nro"),
        ("Total", "total"),
    ):
        stock = rbi(40, "nri_dep", subject, "outstanding", "m", "08-019", "usd", agg="end")
        put("M18", "Outstanding", label, stock)
        flow = rbi(40, "nri_dep", subject, "flow", "m", "08-019", "usd", agg="sum")
        put("M18", "Inflows(+)/outflows(−)", label, flow)

    for label, subject in (
        ("Merchant", "merchant"),
        ("Inter-bank", "interbank"),
        ("Total", "total"),
    ):
        put("M19", "Turnover", label, rbi(30, "fx_turnover", subject, "usd", "m", "08-018", "usd"))

    for label in INDIA_MARKETS:
        put("D01", "Daily close", label, yahoo(label))
        put("W01", "Friday close", label, yahoo(label), agg="end")
        put("M25", "Month-end close", label, yahoo(label), agg="end")
    for label in ("Nifty 50", "Sensex", "Nifty Bank", "India VIX"):
        put("M25", "Monthly average close", label, yahoo(label), agg="mean")

    for label in FX_YAHOO + ["US Dollar Index"]:
        put("D02", "Market rate (Yahoo)", label, yahoo(label))
    for label in COMMODITIES:
        put("D03", "International futures (Yahoo)", label, yahoo(label))
    for label in GLOBAL_INDICES + ["US 10Y yield (%)", "US VIX"]:
        put("D04", "Daily close", label, yahoo(label))
    for label in GLOBAL_MARKETS:
        put("W02", "Friday close", label, yahoo(label), agg="end")
        put("M26", "Month-end close", label, yahoo(label), agg="end")
    for label in (
        "USD/INR",
        "Brent (US$/bbl)",
        "Gold (US$/oz)",
        "US Dollar Index",
        "US 10Y yield (%)",
    ):
        put("M26", "Monthly average", label, yahoo(label), agg="mean")

    renewables = [("Solar", "solar"), ("Wind", "wind"), ("Hydro", "hydro"), ("Bio power", "bio")]
    for code, (label, subject) in enumerate(renewables + [("Total", "total")], start=1):
        params = {"indicator_code": code}
        capacity = simple(
            "re_cap", "MNRE", subject, "mw", "m", "MW", "end", "11-005", source_params=params
        )
        put("M28", "Installed capacity", label, capacity)

    # ---- Occasional (survey rounds: explicit periods, no FY basis) --------------------------
    hces = {
        "Monthly per capita expenditure": [
            ("Rural MPCE", "rural.mpce", "₹ per month"),
            ("Urban MPCE", "urban.mpce", "₹ per month"),
            ("Rural MPCE (with imputation)", "rural.mpce_imputed", "₹ per month"),
            ("Urban MPCE (with imputation)", "urban.mpce_imputed", "₹ per month"),
        ],
        "Distribution": [
            ("Gini – rural", "rural.gini", "ratio"),
            ("Gini – urban", "urban.gini", "ratio"),
            ("Food share – rural %", "rural.food_share", "percent"),
            ("Food share – urban %", "urban.food_share", "percent"),
        ],
    }
    for blk, items in hces.items():
        for label, subject, unit in items:
            survey = simple(
                "hces", "HCES", subject, None, "o", unit, "none", "14-001", period_basis=None
            )
            put("O05", blk, label, survey)

    for label, subject, unit in [
        ("Total fertility rate", "tfr", "children per woman"),
        ("Infant mortality rate", "imr", "per 1,000 live births"),
        ("Stunting (under 5) %", "stunting_u5", "percent"),
        ("Wasting (under 5) %", "wasting_u5", "percent"),
        ("Anaemia – women %", "anaemia_women", "percent"),
        ("Institutional births %", "institutional_births", "percent"),
    ]:
        survey = simple(
            "nfhs", "NFHS", subject, None, "o", unit, "none", "14-002", period_basis=None
        )
        put("O07", "All-India", label, survey)

    return cells
