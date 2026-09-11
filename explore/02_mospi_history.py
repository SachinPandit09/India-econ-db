"""
STEP 2 - How much history does each important MoSPI series have?

For the economically important datasets (CPI, IIP, WPI, NAS/GDP, PLFS, RBI,
CPI-AL/RL, ISP, ENERGY, MNRE, ASI) this asks the API which years/months/quarters
are available for every indicator and base year, then saves:

  output/mospi_history.xlsx      -> HISTORY sheet: earliest, latest, number of periods
                                    SAMPLES sheets: a few real data pulls
  output/mospi_meta/*.json       -> raw metadata for each probe

No API key needed. Takes roughly 5-15 minutes (many small requests).
Run:  python 02_mospi_history.py
"""
import re
import time

import esankhyiki
import pandas as pd

from common import OUT, YEAR_RE, quiet, save_json, sheet_name, tables_in, year_like_values

MAX_INDICATORS_PER_DATASET = 40   # safety cap
PAUSE = 0.4                       # seconds between requests

rows = []


def sort_key(v: str):
    m = YEAR_RE.search(v)
    return (int(m.group()) if m else 9999, v)


def probe(dataset: str, label: str, **kwargs):
    """Ask get_metadata for one combination and record the period coverage."""
    print(f"  {dataset:<8} {label:<60}", end=" ", flush=True)
    rec = {"dataset": dataset, "probe": label, "params": str(kwargs)}
    try:
        with quiet():
            meta = esankhyiki.get_metadata(dataset, **kwargs)
        fname = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{dataset}_{label}")[:120]
        save_json(meta, OUT / "mospi_meta" / f"{fname}.json")
        if isinstance(meta, dict) and meta.get("error"):
            raise RuntimeError(meta["error"])

        periods = year_like_values(meta)
        if not periods:
            rows.append({**rec, "status": "OK (no period list found - check JSON)"})
            print("OK, no period field")
            return
        for field, values in periods.items():
            vals = sorted({str(v) for v in values}, key=sort_key)
            rows.append({
                **rec, "status": "OK",
                "period_field": field.replace("root.", ""),
                "n_periods": len(vals),
                "earliest": vals[0] if vals else "",
                "latest": vals[-1] if vals else "",
                "all_values": ", ".join(vals)[:3000],
            })
        first = next(iter(periods.values()))
        print(f"OK   {len(first)} periods")
    except Exception as e:
        rows.append({**rec, "status": f"FAILED: {type(e).__name__}", "all_values": str(e)[:300]})
        print(f"FAILED  {type(e).__name__}")
    time.sleep(PAUSE)


def indicator_list(dataset: str):
    """Return [(group, code, name)] from get_indicators, whatever the response shape."""
    with quiet():
        result = esankhyiki.get_indicators(dataset)
    out = []
    for path, df in tables_in(result):
        cols = list(df.columns)
        code_col = next((c for c in cols if re.fullmatch(r"(sub_)?indicator_code", c, re.I)), None) \
            or next((c for c in cols if re.search(r"code", c, re.I)), None)
        name_col = next((c for c in cols if re.search(r"name|description|indicator$", c, re.I)
                         and c != code_col), None)
        if code_col is None:
            continue
        for _, r in df.iterrows():
            out.append((path, r[code_col], r[name_col] if name_col else ""))
    return out[:MAX_INDICATORS_PER_DATASET]


print("Checking history coverage...\n")

# ---- Prices -------------------------------------------------------------
for by in ["2024", "2012"]:
    for level in ["Group", "Item"]:
        probe("CPI", f"base {by} | {level} | Current", base_year=by, level=level, series="Current")
probe("CPI", "base 2024 | Group | Back series", base_year="2024", level="Group", series="Back")

for by in ["2022-23", "2011-12"]:
    probe("WPI", f"base {by}", base_year=by)

# ---- Industry -----------------------------------------------------------
for by in ["2022-23", "2011-12"]:
    for freq in ["Monthly", "Annually"]:
        probe("IIP", f"base {by} | {freq}", base_year=by, frequency=freq)

for cy in ["2008", "2004"]:
    probe("ASI", f"NIC classification {cy}", classification_year=cy)

for fc, lab in [(1, "Yearly"), (2, "Monthly")]:
    probe("ISP", f"frequency {lab}", frequency_code=fc)

# ---- National accounts (GDP, GVA ...) -----------------------------------
# MoSPI's NAS indicator-list endpoint sometimes returns HTTP 500. The API spec says
# NAS indicator codes run from 1 to 22, so fall back to probing those directly.
try:
    nas_indicators = [(code, str(name)[:30]) for _, code, name in indicator_list("NAS")]
    if not nas_indicators:
        raise RuntimeError("empty list")
except Exception as e:
    print(f"  NAS indicator list unavailable ({type(e).__name__}) - probing codes 1..22 directly")
    nas_indicators = [(code, "") for code in range(1, 23)]

for code, short in nas_indicators:
    for by in ["2022-23", "2011-12"]:
        for fc, lab in [(1, "Annual"), (2, "Quarterly")]:
            probe("NAS", f"{code} {short} | base {by} | {lab}",
                  indicator_code=int(code), base_year=by, frequency_code=fc, series="Current")
    probe("NAS", f"{code} {short} | base 2022-23 | Annual | Back",
          indicator_code=int(code), base_year="2022-23", frequency_code=1, series="Back")

# ---- Labour (PLFS) ------------------------------------------------------
try:
    for group, code, name in indicator_list("PLFS"):
        m = re.search(r"frequency_code_(\d)", group)
        fc = int(m.group(1)) if m else 1
        probe("PLFS", f"{code} {str(name)[:35]} | freq {fc}",
              indicator_code=int(code), frequency_code=fc)
except Exception as e:
    print(f"  PLFS indicator list failed: {e}")

# ---- Other monthly/annual economic datasets -----------------------------
for ds in ["RBI", "CPIALRL", "ENERGY"]:
    try:
        for _, code, name in indicator_list(ds):
            probe(ds, f"{code} {str(name)[:45]}", indicator_code=int(code))
    except Exception as e:
        print(f"  {ds} indicator list failed: {e}")

for code, name in [(1, "Solar"), (2, "Wind"), (3, "Hydro"), (4, "Bio"), (5, "Total")]:
    probe("MNRE", f"{code} {name}", indicator_code=code)

# ---- A few real data pulls so you can see the actual shape --------------
print("\nFetching sample data...")
samples = {
    "GDP_NAS_2022-23_annual": ("NAS", {"indicator_code": 1, "base_year": "2022-23",
                                       "series": "Current", "frequency_code": 1}),
    "CPI_2024_year2026": ("CPI", {"base_year": "2024", "year": "2026", "series": "Current"}),
    "PLFS_unemployment_2023-24": ("PLFS", {"indicator_code": 3, "frequency_code": 1, "year": "2023-24",
                                           "state_code": 99, "gender_code": 3, "age_code": 1,
                                           "sector_code": 3}),
}
sample_tables = {}


def fetch_all(ds, filters, page_size=100, max_pages=50):
    """MoSPI returns 10 rows per page by default - keep asking for pages until done."""
    parts = []
    for page in range(1, max_pages + 1):
        try:
            with quiet():
                df = esankhyiki.get_data(ds, {**filters, "limit": page_size, "page": page}, format="df")
        except esankhyiki.NoDataError:
            break
        if df is None or df.empty:
            break
        parts.append(df)
        if len(df) < page_size:
            break
        time.sleep(PAUSE)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


for name, (ds, filters) in samples.items():
    try:
        df = fetch_all(ds, filters)
        sample_tables[name] = df
        print(f"  {name:<30} OK   {len(df)} rows")
    except Exception as e:
        print(f"  {name:<30} FAILED  {type(e).__name__}: {str(e)[:80]}")
    time.sleep(PAUSE)

# ---- Save ---------------------------------------------------------------
xlsx = OUT / "mospi_history.xlsx"
with pd.ExcelWriter(xlsx) as xw:
    used = set()
    pd.DataFrame(rows).to_excel(xw, sheet_name=sheet_name("HISTORY", used), index=False)
    for name, df in sample_tables.items():
        df.to_excel(xw, sheet_name=sheet_name("S_" + name, used), index=False)

ok = sum(1 for r in rows if str(r.get("status", "")).startswith("OK"))
print(f"\n{ok}/{len(rows)} probe rows OK. Open: {xlsx}")
print("FAILED usually means that base year / frequency doesn't exist for that indicator -")
print("that is itself useful information.")
