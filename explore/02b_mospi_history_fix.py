"""
STEP 2b - Re-test the datasets that failed in step 2 because my script
did not send parameters they require:

  PLFS   needs year_type_code        (1 = agricultural/financial year, 2 = calendar year)
  RBI    needs sub_indicator_code    (the 39 RBI codes from step 1)
  ENERGY needs use_of_energy_balance_code (1 = Supply, 2 = Consumption)

Also checks the OLDER base years that step 1 revealed but step 2 did not test:
  IIP 2004-05 & 1993-94, WPI 2004-05 & 1993-94, CPI 2010.

Saves: output/mospi_history_2.xlsx  (+ raw JSON in output/mospi_meta/)
Takes roughly 3-8 minutes.
Run:  python 02b_mospi_history_fix.py
"""
import re
import time

import esankhyiki
import pandas as pd

from common import OUT, YEAR_RE, quiet, save_json, sheet_name, tables_in, year_like_values

PAUSE = 0.4
rows = []


def sort_key(v: str):
    m = YEAR_RE.search(v)
    return (int(m.group()) if m else 9999, v)


def probe(dataset: str, label: str, **kwargs):
    print(f"  {dataset:<8} {label:<62}", end=" ", flush=True)
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
            rows.append({**rec, "status": "OK", "period_field": field.replace("root.", ""),
                         "n_periods": len(vals), "earliest": vals[0] if vals else "",
                         "latest": vals[-1] if vals else "", "all_values": ", ".join(vals)[:3000]})
        print(f"OK   {len(next(iter(periods.values())))} periods")
    except Exception as e:
        rows.append({**rec, "status": f"FAILED: {type(e).__name__}", "all_values": str(e)[:300]})
        print(f"FAILED  {type(e).__name__}: {str(e)[:50]}")
    time.sleep(PAUSE)


def codes_from(dataset: str):
    with quiet():
        result = esankhyiki.get_indicators(dataset)
    out = []
    for path, df in tables_in(result):
        code_col = next((c for c in df.columns if re.search(r"indicator_code", c, re.I)), None)
        name_col = next((c for c in df.columns if re.search(r"label|description|name", c, re.I)), None)
        if code_col:
            for _, r in df.dropna(subset=[code_col]).iterrows():
                out.append((path, int(r[code_col]), str(r[name_col])[:45] if name_col else ""))
    return out


print("Re-testing with correct parameters...\n")

# PLFS: every indicator x both year types
for group, code, name in codes_from("PLFS"):
    m = re.search(r"frequency_code_(\d)", group)
    fc = int(m.group(1)) if m else 1
    for yt, ylab in [("1", "agri/FY year"), ("2", "calendar year")]:
        probe("PLFS", f"{code} {name[:28]} | freq {fc} | {ylab}",
              indicator_code=code, frequency_code=fc, year_type_code=yt)

# RBI: all 39 indicators via sub_indicator_code
for _, code, name in codes_from("RBI"):
    probe("RBI", f"{code} {name}", sub_indicator_code=code)

# ENERGY: both indicators x supply/consumption
for code, name in [(1, "Energy Balance KToE"), (2, "Energy Balance PetaJoules")]:
    for uc, ulab in [(1, "Supply"), (2, "Consumption")]:
        probe("ENERGY", f"{code} {name} | {ulab}", indicator_code=code, use_of_energy_balance_code=uc)

# Older base years
for by in ["2004-05", "1993-94"]:
    probe("IIP", f"base {by} | Monthly", base_year=by, frequency="Monthly")
    probe("IIP", f"base {by} | Annually", base_year=by, frequency="Annually")
    probe("WPI", f"base {by}", base_year=by)
probe("CPI", "base 2010 | Group | Current", base_year="2010", level="Group", series="Current")

xlsx = OUT / "mospi_history_2.xlsx"
with pd.ExcelWriter(xlsx) as xw:
    pd.DataFrame(rows).to_excel(xw, sheet_name=sheet_name("HISTORY_2", set()), index=False)

ok = sum(1 for r in rows if str(r.get("status", "")).startswith("OK"))
print(f"\n{ok}/{len(rows)} probe rows OK. Open: {xlsx}")
