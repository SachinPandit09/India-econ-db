"""
Shared helpers for the exploration scripts.
You don't need to run this file directly.
"""
import contextlib
import io
import json
import re
import warnings
from pathlib import Path

import pandas as pd

# The MoSPI package prints every raw API response to the screen and turns off
# SSL checks (the government server needs that). Silence both so output is readable.
warnings.filterwarnings("ignore")
try:
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    pass

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

YEAR_RE = re.compile(r"(19|20)\d{2}")


@contextlib.contextmanager
def quiet():
    """Hide anything a library prints while the block runs."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def tables_in(obj, path="root"):
    """
    Walk any JSON-like object and yield (path, DataFrame) for every list found.
    Lets us turn unknown API response shapes into tables you can read in Excel.
    """
    if isinstance(obj, list) and obj:
        if all(isinstance(x, dict) for x in obj):
            yield path, pd.json_normalize(obj)
        elif all(not isinstance(x, (dict, list)) for x in obj):
            yield path, pd.DataFrame({path.split(".")[-1]: obj})
        else:
            for i, x in enumerate(obj):
                yield from tables_in(x, f"{path}[{i}]")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k == "api_params":  # parameter docs, not data
                continue
            yield from tables_in(v, f"{path}.{k}")


def year_like_values(obj):
    """
    Collect every value under a key whose name mentions year/month/quarter.
    Used to answer 'how far back does history go?'.
    Returns {key_path: [values...]}.
    """
    found = {}

    def label(x):
        if isinstance(x, dict):
            for v in x.values():
                if isinstance(v, str) and YEAR_RE.search(v):
                    return v
            return next((str(v) for v in x.values() if isinstance(v, str)), str(x))
        return str(x)

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{path}.{k}"
                if isinstance(v, list) and re.search(r"year|month|quarter|period", k, re.I):
                    found[p] = [label(x) for x in v]
                else:
                    walk(v, p)
        elif isinstance(o, list):
            for x in o:
                walk(x, path)

    walk(obj, "root")
    return found


def sheet_name(name: str, used: set) -> str:
    """Excel sheet names: max 31 chars, no []:*?/\\ and must be unique."""
    base = re.sub(r"[\[\]:*?/\\]", "_", name)[:31] or "sheet"
    s, i = base, 1
    while s in used:
        suffix = f"_{i}"
        s = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(s)
    return s
