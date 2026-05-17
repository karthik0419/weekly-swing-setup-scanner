"""
Fetches the full NSE EQ-series equity list (~2000+ stocks).
Source: NSE archives (EQUITY_L.csv) — updated daily by NSE.
Cached locally for 7 days.
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "nse_eq_universe.csv")
os.makedirs(CACHE_DIR, exist_ok=True)

NSE_EQ_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": "https://www.nseindia.com/",
}


def _is_fresh(path, max_age_days=7):
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(days=max_age_days)


def fetch_nse_eq_universe():
    """
    Returns list of NSE symbols with .NS suffix.
    Only EQ series — excludes SME, BE, BZ etc.
    Cached for 7 days.
    """
    if _is_fresh(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            if len(df) > 100:
                print(f"  Universe loaded from cache: {len(df)} stocks")
                return df["symbol_ns"].tolist()
        except Exception:
            pass

    print("  Fetching full NSE EQ list from archives.nseindia.com...")
    try:
        resp = requests.get(NSE_EQ_URL, headers=HEADERS, timeout=30)
        if resp.status_code != 200 or len(resp.content) < 1000:
            print(f"  Fetch failed (status {resp.status_code}) — using cache if available")
            return _load_cache_fallback()

        df = pd.read_csv(StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]

        # Keep only main-board EQ series
        if "SERIES" in df.columns:
            df = df[df["SERIES"].str.strip() == "EQ"]

        sym_col = next((c for c in df.columns if "SYMBOL" in c.upper()), None)
        if sym_col is None:
            print("  Symbol column not found")
            return _load_cache_fallback()

        symbols = df[sym_col].dropna().str.strip().str.upper().tolist()
        symbols = [s for s in symbols if s and len(s) <= 20 and not s.startswith("DUMMY")]

        result = pd.DataFrame({
            "symbol":    symbols,
            "symbol_ns": [s + ".NS" for s in symbols],
        })
        result.to_csv(CACHE_FILE, index=False)
        print(f"  NSE EQ universe fetched: {len(result)} stocks")
        return result["symbol_ns"].tolist()

    except Exception as e:
        print(f"  Fetch error: {e}")
        return _load_cache_fallback()


def _load_cache_fallback():
    try:
        df = pd.read_csv(CACHE_FILE)
        print(f"  Using stale cache: {len(df)} stocks")
        return df["symbol_ns"].tolist()
    except Exception:
        print("  No cache available — returning empty list")
        return []
