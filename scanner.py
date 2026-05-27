"""
Weekly Swing Setup Scanner
Scans full NSE EQ universe (~2000+ stocks) for swing trading patterns.
Run every Saturday for a full deep scan.

Usage:
  python scanner.py                  # full scan, top 30
  python scanner.py --top 50         # top 50 results
  python scanner.py --min-score 80   # higher quality filter
  python scanner.py --test           # quick test on 50 stocks
"""

import os
import sys
import time
import argparse
import warnings
import pandas as pd
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.nse_eq import fetch_nse_eq_universe
from data.loader import _fetch_nse, _resample_weekly
from patterns.cup_handle import detect_cup_handle, detect_cup_handle_weekly
from patterns.breakout import detect_breakout
from patterns.break_retest import detect_break_retest
from patterns.channel import detect_descending_channel, detect_ascending_channel
from patterns.triangle import detect_triangle
from patterns.darvas_box import detect_darvas_box
from patterns.flags import detect_flag_pennant
from patterns.sr_levels import detect_sr_levels
from patterns.double_top_bottom import detect_double_bottom
from patterns.retest import detect_retest
from patterns.compression import detect_compression

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

MIN_CANDLES = 140
MAX_WORKERS = 4


def _detect_pattern(df_daily, df_weekly):
    """Run all pattern detectors in priority order."""
    return (
        detect_cup_handle_weekly(df_weekly) or
        detect_cup_handle(df_daily) or
        detect_double_bottom(df_daily) or
        detect_descending_channel(df_daily) or
        detect_ascending_channel(df_daily) or
        detect_triangle(df_daily) or
        detect_darvas_box(df_daily) or
        detect_flag_pennant(df_daily) or
        detect_sr_levels(df_daily) or
        detect_break_retest(df_daily) or
        detect_retest(df_daily) or
        detect_compression(df_daily) or
        detect_breakout(df_daily)
    )


def _score(result):
    """Simple RR-based score."""
    cmp      = result.get("cmp", 0)
    target   = result.get("target", 0)
    stop     = result.get("stop_loss", 0)
    breakout = result.get("breakout", 0)

    if cmp <= 0 or stop <= 0 or stop >= cmp:
        return 0, 0

    upside = (target - cmp) / cmp * 100
    risk   = (cmp - stop) / cmp * 100
    rr     = upside / risk if risk > 0 else 0

    score = 0
    if rr >= 3:   score += 40
    elif rr >= 2: score += 30
    elif rr >= 1: score += 15

    if result.get("volume"):        score += 15
    if result.get("status") == "NEAR":     score += 10
    if result.get("status") == "BREAKOUT": score += 20

    dist = abs(cmp - breakout) / breakout if breakout else 1
    if dist < 0.02:  score += 20
    elif dist < 0.05: score += 12
    elif dist < 0.10: score += 6

    pat = result.get("pattern", "")
    pat_bonus = {
        "Cup & Handle (Weekly)": 25,
        "Cup & Handle":          20,
        "Double Bottom":         18,
        "Ascending Triangle":    15,
        "Symmetrical Triangle":  12,
        "Darvas Box":            15,
        "Bullish Flag":          12,
        "Break & Retest":        10,
        "S&R Breakout":          10,
        "Channel Breakout (Descending)": 22,
        "Channel Breakout (Ascending)":  18,
        "Channel Breakout":              10,
    }
    score += pat_bonus.get(pat, 5)

    return round(score, 1), round(rr, 2)


def _analyse(symbol):
    """Full analysis for one stock. Returns result dict or None."""
    try:
        df = _fetch_nse(symbol.replace(".NS", ""), days=365)
        if df is None or len(df) < MIN_CANDLES:
            return None

        df_weekly = _resample_weekly(df)
        result = _detect_pattern(df, df_weekly)
        if not result:
            return None

        score, rr = _score(result)
        if rr <= 0 or score < 10:
            return None

        cmp    = result.get("cmp", 0)
        target = result.get("target", 0)
        stop   = result.get("stop_loss", 0)
        upside = round((target - cmp) / cmp * 100, 2) if cmp else 0
        risk   = round((cmp - stop) / cmp * 100, 2) if cmp else 0

        return {
            "symbol":   symbol,
            "pattern":  result.get("pattern"),
            "status":   result.get("status"),
            "cmp":      round(cmp, 2),
            "breakout": round(result.get("breakout", 0), 2),
            "stop_loss":round(stop, 2),
            "target":   round(target, 2),
            "upside_%": upside,
            "risk_%":   risk,
            "rr":       rr,
            "volume":   result.get("volume", False),
            "score":    score,
        }
    except Exception:
        return None


def _fetch_price_parallel(symbols, workers=MAX_WORKERS):
    """Pre-fetch price data in parallel to speed up scan."""
    print(f"  Pre-fetching price data ({workers} workers)...")
    from data.loader import _fetch_nse as fn
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fn, s.replace(".NS", ""), 365): s for s in symbols}
        done = 0
        for f in as_completed(futures, timeout=600):
            done += 1
            sym = futures[f]
            try:
                df = f.result(timeout=30)
                if df is not None and len(df) >= MIN_CANDLES:
                    results[sym] = df
            except Exception:
                pass
            if done % 100 == 0:
                print(f"    Fetched {done}/{len(symbols)}...")
    print(f"  Price data ready: {len(results)} stocks with enough history")
    return results


def main():
    parser = argparse.ArgumentParser(description="Weekly Swing Setup Scanner — Full NSE EQ")
    parser.add_argument("--top",       type=int,   default=30)
    parser.add_argument("--min-score", type=float, default=50)
    parser.add_argument("--workers",   type=int,   default=MAX_WORKERS)
    parser.add_argument("--test",      action="store_true", help="Quick test on first 50 stocks")
    args = parser.parse_args()

    print("=" * 65)
    print("  WEEKLY SWING SETUP SCANNER")
    print(f"  Full NSE EQ Universe | Date: {date.today()}")
    print("=" * 65)

    # Step 1: Get universe
    print("\n[1/4] Loading NSE EQ universe...")
    symbols = fetch_nse_eq_universe()
    if not symbols:
        print("  Failed to load universe. Exiting.")
        return

    if args.test:
        symbols = symbols[:50]
        print(f"  TEST MODE: scanning first {len(symbols)} stocks only")
    else:
        print(f"  Universe: {len(symbols)} stocks")

    # Step 2: Pre-fetch price data in parallel
    print(f"\n[2/4] Pre-fetching price data...")
    price_cache = _fetch_price_parallel(symbols, workers=args.workers)

    # Step 3: Scan each stock
    print(f"\n[3/4] Scanning {len(price_cache)} stocks for patterns...\n")

    results = []
    total   = len(price_cache)
    scanned = 0

    for sym, df in price_cache.items():
        scanned += 1
        try:
            df_weekly = _resample_weekly(df)
            result = _detect_pattern(df, df_weekly)
            if not result:
                continue

            score, rr = _score(result)
            if rr <= 0 or score < args.min_score:
                continue

            cmp    = result.get("cmp", 0)
            target = result.get("target", 0)
            stop   = result.get("stop_loss", 0)
            upside = round((target - cmp) / cmp * 100, 2) if cmp else 0
            risk   = round((cmp - stop) / cmp * 100, 2) if cmp else 0

            row = {
                "symbol":   sym,
                "pattern":  result.get("pattern"),
                "status":   result.get("status"),
                "cmp":      round(cmp, 2),
                "breakout": round(result.get("breakout", 0), 2),
                "stop_loss":round(stop, 2),
                "target":   round(target, 2),
                "upside_%": upside,
                "risk_%":   risk,
                "rr":       rr,
                "score":    score,
            }
            results.append(row)
            print(f"  [{scanned:>4}/{total}] {sym:<20} FOUND | {result.get('pattern')} | score={score} | rr={rr}")

        except Exception:
            continue

    # Step 4: Save & report
    print(f"\n[4/4] Saving results...")

    if not results:
        print("  No setups found. Try lowering --min-score.")
        return

    df_out   = pd.DataFrame(results).sort_values("score", ascending=False).head(args.top)
    out_path = os.path.join(RESULTS_DIR, f"weekly_{date.today()}.csv")
    df_out.to_csv(out_path, index=False)

    print(f"\n{'=' * 65}")
    print(f"  SCAN COMPLETE — {date.today()}")
    print(f"  Stocks scanned  : {total}")
    print(f"  Setups found    : {len(results)}")
    print(f"  Top score       : {df_out['score'].iloc[0]} ({df_out['symbol'].iloc[0]})")
    print(f"{'=' * 65}")
    print(f"\n  TOP {len(df_out)} SETUPS")
    print(f"  {'Symbol':<20} {'Pattern':<25} {'Score':>5} {'RR':>5} {'Upside%':>8} {'Status'}")
    print("  " + "-" * 75)
    for _, row in df_out.iterrows():
        print(f"  {row['symbol']:<20} {row['pattern']:<25} {row['score']:>5} "
              f"{row['rr']:>5} {row['upside_%']:>7}%  {row['status']}")

    print(f"\n  Saved to: {out_path}")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()
