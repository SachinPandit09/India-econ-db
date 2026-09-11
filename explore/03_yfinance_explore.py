"""
STEP 3 - What market data can Yahoo Finance (yfinance) give us for India?

Part A: tests a list of Indian indices, INR exchange rates, commodities and
        global markets. For each: does it work, first date, last date, rows.
Part B: shows every kind of data yfinance has for one Indian stock
        (company info fields, financial statements, dividends...).

Saves: output/yfinance_explore.xlsx
No API key needed. Takes 2-4 minutes. Add or remove tickers in TICKERS below.
Run:  python 03_yfinance_explore.py
"""
import time

import pandas as pd
import yfinance as yf

from common import OUT, sheet_name

TICKERS = {
    # --- Indian indices ---
    "^NSEI": "Nifty 50", "^BSESN": "Sensex", "^NSEBANK": "Nifty Bank",
    "^CNXIT": "Nifty IT", "^CNXAUTO": "Nifty Auto", "^CNXFMCG": "Nifty FMCG",
    "^CNXPHARMA": "Nifty Pharma", "^CNXMETAL": "Nifty Metal", "^CNXREALTY": "Nifty Realty",
    "^CNXENERGY": "Nifty Energy", "^CNXPSUBANK": "Nifty PSU Bank", "^CNXINFRA": "Nifty Infra",
    "^CNXMEDIA": "Nifty Media", "^NSEMDCP50": "Nifty Midcap 50", "^CNXSC": "Nifty Smallcap 100",
    "^CRSLDX": "Nifty 500", "^INDIAVIX": "India VIX",
    # --- Indian ETFs / stocks (samples) ---
    "NIFTYBEES.NS": "Nifty BeES ETF", "GOLDBEES.NS": "Gold BeES ETF",
    "RELIANCE.NS": "Reliance (NSE)", "HDFCBANK.NS": "HDFC Bank (NSE)", "500325.BO": "Reliance (BSE code)",
    # --- Rupee exchange rates ---
    "INR=X": "USD/INR", "EURINR=X": "EUR/INR", "GBPINR=X": "GBP/INR",
    "JPYINR=X": "JPY/INR", "CNYINR=X": "CNY/INR", "AEDINR=X": "AED/INR",
    # --- Commodities (futures, USD) ---
    "GC=F": "Gold", "SI=F": "Silver", "CL=F": "WTI crude", "BZ=F": "Brent crude",
    "NG=F": "Natural gas", "HG=F": "Copper",
    # --- Global markets ---
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones", "^N225": "Nikkei 225",
    "^HSI": "Hang Seng", "^FTSE": "FTSE 100", "DX-Y.NYB": "US Dollar Index",
    "^TNX": "US 10Y yield", "^VIX": "US VIX",
}
FUNDAMENTALS_TICKER = "RELIANCE.NS"
PAUSE = 1.5  # Yahoo rate-limits fast requests; keep this

print(f"yfinance version {yf.__version__}\n\nPart A - testing {len(TICKERS)} tickers (full history)...\n")
summary, closes = [], {}
for t, name in TICKERS.items():
    print(f"  {t:<14} {name:<22}", end=" ", flush=True)
    try:
        h = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=False)
        if h.empty:
            raise ValueError("no data returned")
        idx = h.index.tz_localize(None) if h.index.tz is not None else h.index
        s = pd.Series(h["Close"].values, index=idx.normalize())
        closes[f"{t} | {name}"] = s[~s.index.duplicated(keep="last")]
        summary.append({
            "ticker": t, "name": name, "status": "OK",
            "first_date": idx.min().date(), "last_date": idx.max().date(),
            "years_of_history": round((idx.max() - idx.min()).days / 365.25, 1),
            "rows": len(h), "last_close": round(float(h["Close"].iloc[-1]), 2),
            "has_volume": bool(h["Volume"].fillna(0).gt(0).any()),
        })
        print(f"OK   {idx.min().date()} -> {idx.max().date()}  ({len(h)} rows)")
    except Exception as e:
        summary.append({"ticker": t, "name": name, "status": f"FAILED: {str(e)[:120]}"})
        print(f"FAILED  {str(e)[:60]}")
    time.sleep(PAUSE)

print(f"\nPart B - everything yfinance offers for {FUNDAMENTALS_TICKER}...\n")
tk = yf.Ticker(FUNDAMENTALS_TICKER)
fund_sheets, catalogue = {}, []


def grab(label, fn):
    print(f"  {label:<26}", end=" ", flush=True)
    try:
        obj = fn()
        if isinstance(obj, dict):
            df = pd.DataFrame(list(obj.items()), columns=["field", "value"])
        elif isinstance(obj, pd.Series):
            df = obj.to_frame("value")
            df.index = df.index.astype(str)
            df = df.reset_index()
        elif isinstance(obj, pd.DataFrame):
            df = obj.copy()
            df.columns = [str(c) for c in df.columns]
            df = df.reset_index()
        else:
            df = pd.DataFrame({"value": [str(obj)]})
        for c in df.columns:  # Excel can't store timezone-aware dates
            if hasattr(df[c], "dt") and getattr(df[c].dt, "tz", None) is not None:
                df[c] = df[c].dt.tz_localize(None)
        fund_sheets[label] = df
        catalogue.append({"data_type": label, "status": "OK", "rows": len(df), "columns": len(df.columns)})
        print(f"OK   {len(df)} rows x {len(df.columns)} cols")
    except Exception as e:
        catalogue.append({"data_type": label, "status": f"FAILED: {str(e)[:120]}"})
        print(f"FAILED  {str(e)[:60]}")
    time.sleep(PAUSE)


grab("info (company fields)", lambda: tk.info)
grab("income_stmt annual", lambda: tk.income_stmt)
grab("income_stmt quarterly", lambda: tk.quarterly_income_stmt)
grab("balance_sheet annual", lambda: tk.balance_sheet)
grab("balance_sheet quarterly", lambda: tk.quarterly_balance_sheet)
grab("cashflow annual", lambda: tk.cashflow)
grab("cashflow quarterly", lambda: tk.quarterly_cashflow)
grab("dividends", lambda: tk.dividends)
grab("splits", lambda: tk.splits)
grab("major_holders", lambda: tk.major_holders)
grab("recommendations", lambda: tk.recommendations)
grab("earnings_dates", lambda: tk.earnings_dates)

xlsx = OUT / "yfinance_explore.xlsx"
with pd.ExcelWriter(xlsx) as xw:
    used = set()
    pd.DataFrame(summary).to_excel(xw, sheet_name=sheet_name("TICKERS", used), index=False)
    if closes:
        wide = pd.DataFrame(closes).sort_index()
        wide.index.name = "date"
        wide.to_excel(xw, sheet_name=sheet_name("DAILY_CLOSES", used))
    pd.DataFrame(catalogue).to_excel(xw, sheet_name=sheet_name("FUNDAMENTALS_LIST", used), index=False)
    for label, df in fund_sheets.items():
        df.to_excel(xw, sheet_name=sheet_name(label, used), index=False)

ok = sum(1 for s in summary if s["status"] == "OK")
print(f"\n{ok}/{len(TICKERS)} tickers worked. Open: {xlsx}")
print("If many fail with 'Too Many Requests', wait an hour and re-run (Yahoo rate limit).")
