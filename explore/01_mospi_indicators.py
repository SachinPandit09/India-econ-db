"""
STEP 1 - What indicators does the MoSPI API offer?

Calls get_indicators() for all 30 MoSPI datasets and saves:
  output/mospi_indicators.xlsx   -> SUMMARY sheet + one sheet per dataset
  output/mospi_raw/<DATASET>.json -> the raw response, if you want to dig deeper

No API key needed. Takes 1-3 minutes.
Run:  python 01_mospi_indicators.py
"""
import time

import esankhyiki
import pandas as pd

from common import OUT, quiet, save_json, sheet_name, tables_in

datasets = esankhyiki.list_datasets()["datasets"]
print(f"MoSPI lists {len(datasets)} datasets\n")

summary, sheets = [], {}

for ds in datasets:
    print(f"  {ds:<10}", end=" ", flush=True)
    try:
        with quiet():
            result = esankhyiki.get_indicators(ds)
        save_json(result, OUT / "mospi_raw" / f"{ds}.json")

        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(result["error"])

        # Stack every table found in the response into one sheet for this dataset
        parts = []
        for path, df in tables_in(result):
            df.insert(0, "group", path.replace("root.", ""))
            parts.append(df)
        table = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        sheets[ds] = table
        summary.append({"dataset": ds, "status": "OK", "rows_listed": len(table), "note": ""})
        print(f"OK   {len(table)} rows")
    except Exception as e:
        summary.append({"dataset": ds, "status": "FAILED", "rows_listed": 0, "note": str(e)[:200]})
        print(f"FAILED  {str(e)[:80]}")
    time.sleep(0.5)  # be polite to the government server

xlsx = OUT / "mospi_indicators.xlsx"
with pd.ExcelWriter(xlsx) as xw:
    used = set()
    pd.DataFrame(summary).to_excel(xw, sheet_name=sheet_name("SUMMARY", used), index=False)
    for ds, df in sheets.items():
        if not df.empty:
            df.to_excel(xw, sheet_name=sheet_name(ds, used), index=False)

ok = sum(1 for s in summary if s["status"] == "OK")
print(f"\n{ok}/{len(datasets)} datasets answered. Open: {xlsx}")
print("Notes: CPI lists base years (not indicators). IIP and WPI have no sub-indicators;")
print("       their detail appears in step 2 (02_mospi_history.py).")
