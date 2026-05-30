"""Generate candlestick charts with breakout/SL/target levels for selected stocks."""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mplfinance as mpf
from data.loader import _fetch_nse, _resample_weekly
from scanner import _detect_pattern

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "charts")
os.makedirs(OUT_DIR, exist_ok=True)

STOCKS = ["DEEPINDS", "LEMONTREE", "ELGIEQUIP", "ACMESOLAR", "SANDUMA"]


def plot(symbol):
    df = _fetch_nse(symbol, days=365)
    if df is None or len(df) < 140:
        print(f"  {symbol}: insufficient data")
        return
    res = _detect_pattern(df, _resample_weekly(df))
    if not res:
        print(f"  {symbol}: no pattern")
        return

    df = df.tail(180).copy()
    df.index.name = "Date"

    cmp_      = res.get("cmp", 0)
    breakout  = res.get("breakout", 0)
    stop      = res.get("stop_loss", 0)
    target    = res.get("target", 0)
    pattern   = res.get("pattern", "")
    status    = res.get("status", "")

    hlines = dict(
        hlines=[breakout, stop, target, cmp_],
        colors=["blue", "red", "green", "black"],
        linestyle=["--", "--", "--", "-"],
        linewidths=[1.2, 1.2, 1.2, 0.8],
    )

    title = f"{symbol}  |  {pattern}  ({status})\nCMP {cmp_:.2f}  BO {breakout:.2f}  SL {stop:.2f}  TGT {target:.2f}"
    out = os.path.join(OUT_DIR, f"{symbol}.png")

    mpf.plot(
        df,
        type="candle",
        style="yahoo",
        volume=True,
        mav=(20, 50),
        hlines=hlines,
        title=title,
        figsize=(13, 7),
        savefig=dict(fname=out, dpi=120, bbox_inches="tight"),
    )
    print(f"  {symbol}: saved -> {out}")


if __name__ == "__main__":
    print(f"Saving charts to: {OUT_DIR}\n")
    for s in STOCKS:
        plot(s)
    print("\nDone.")
