"""
STEP 4 - Test the data.gov.in API (needs a free API key).

1. Put your key in the .env file in this folder:   DATAGOVIN_API_KEY=your_key_here
2. Run with the default dataset (daily mandi commodity prices):
       python 04_datagovin_test.py
   or with any dataset's Resource ID copied from its data.gov.in page:
       python 04_datagovin_test.py <resource_id> [number_of_records]

Saves: output/datagovin_<resource_id>.xlsx
"""
import os
import re
import sys
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from common import OUT

load_dotenv()
KEY = os.getenv("DATAGOVIN_API_KEY", "").strip()
if not KEY:
    sys.exit("No key found. Add DATAGOVIN_API_KEY=... to the .env file in this folder.")

# Default: 'Current Daily Price of Various Commodities from Various Markets (Mandi)'
resource_id = sys.argv[1] if len(sys.argv) > 1 else "9ef84268-d588-465a-a308-a864a43d0070"
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

# A resource ID looks like 8-4-4-4-12 hex characters, e.g. 9ef84268-d588-465a-a308-a864a43d0070
if not re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", resource_id):
    sys.exit(f"'{resource_id}' is not a valid resource ID. Copy the full ID from the dataset's API tab.")

url = f"https://api.data.gov.in/resource/{resource_id}"
params = {"api-key": KEY, "format": "json", "limit": limit, "offset": 0}
# Government servers often stall requests that don't look like a browser
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}

data = None
for attempt in range(1, 4):
    print(f"Attempt {attempt}/3: requesting {limit} records from {url} ...", flush=True)
    try:
        r = requests.get(url, params=params, headers=headers, timeout=(15, 120))
        print(f"HTTP {r.status_code}")
        r.raise_for_status()
        data = r.json()
        break
    except requests.exceptions.Timeout:
        print("  Timed out - the server is slow. Waiting 10s and retrying...")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"  Server refused the request: {e}\n  Response: {r.text[:300]}")
    except ValueError:
        sys.exit(f"  Server did not return JSON. First 300 chars:\n{r.text[:300]}")
    time.sleep(10)

if data is None:
    sys.exit("data.gov.in did not answer after 3 tries. Test the same URL in your browser "
             "(see instructions) to check whether the server itself is down.")

print(f"\nTitle        : {data.get('title')}")
print(f"Total records: {data.get('total')}")
print(f"Last updated : {data.get('updated_date')}")
fields = data.get("field", [])
print(f"Fields ({len(fields)}): " + ", ".join(f.get("id", "") for f in fields))

records = pd.DataFrame(data.get("records", []))
print(f"\nFirst rows:\n{records.head(10).to_string()}")

xlsx = OUT / f"datagovin_{resource_id[:8]}.xlsx"
with pd.ExcelWriter(xlsx) as xw:
    records.to_excel(xw, sheet_name="RECORDS_sample", index=False)
    pd.DataFrame(fields).to_excel(xw, sheet_name="FIELDS", index=False)
    meta = {k: v for k, v in data.items() if k not in ("records", "field")}
    pd.DataFrame(list(meta.items()), columns=["key", "value"]).astype(str) \
        .to_excel(xw, sheet_name="METADATA", index=False)
print(f"\nSaved: {xlsx}")
