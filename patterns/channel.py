"""
Channel Breakout Detection (Weekly Scanner Edition)

Two detectors:
1. detect_descending_channel — finds long downtrend channels that broke upward
   (like HIKAL: 1-year falling channel, just broke above upper line)
2. detect_ascending_channel  — finds uptrending channels that broke even higher
   (continuation breakouts in already-trending stocks)

Both use lookback=200 bars (~10 months) for catching long-term channel patterns.
"""

import numpy as np


def _fit_trendline(indices, values):
    """Fit a linear trendline. Returns (slope, intercept)."""
    coeffs = np.polyfit(indices, values, 1)
    return coeffs[0], coeffs[1]


def _find_swings(highs, lows, n, window=4):
    swing_high_idx, swing_high_val = [], []
    swing_low_idx, swing_low_val = [], []
    for i in range(window, n - window):
        if highs[i] == max(highs[i - window: i + window + 1]):
            swing_high_idx.append(i)
            swing_high_val.append(highs[i])
        if lows[i] == min(lows[i - window: i + window + 1]):
            swing_low_idx.append(i)
            swing_low_val.append(lows[i])
    return swing_high_idx, swing_high_val, swing_low_idx, swing_low_val


def _channel_breakout(df, lookback, direction, min_touches=3):
    """
    Core detector for both descending and ascending channels.
    direction: 'desc' for falling channel, 'asc' for rising channel.
    """
    if df is None or len(df) < lookback + 10:
        return None

    try:
        df_slice = df.tail(lookback + 10)
        highs  = df_slice['High'].values
        lows   = df_slice['Low'].values
        closes = df_slice['Close'].values
        vols   = df_slice['Volume'].values
        n      = len(df_slice)

        cmp     = float(closes[-1])
        avg_vol = float(np.mean(vols[-20:]))
        cur_vol = float(vols[-1])

        sh_idx, sh_val, sl_idx, sl_val = _find_swings(highs, lows, n)

        if len(sh_idx) < min_touches or len(sl_idx) < min_touches:
            return None

        h_slope, h_int = _fit_trendline(sh_idx, sh_val)
        l_slope, l_int = _fit_trendline(sl_idx, sl_val)

        if direction == "desc":
            if h_slope >= -0.05 or l_slope >= -0.05:
                return None
            pattern_name = "Channel Breakout (Descending)"
        else:
            if h_slope <= 0.05 or l_slope <= 0.05:
                return None
            pattern_name = "Channel Breakout (Ascending)"

        if abs(h_slope) == 0:
            return None
        slope_ratio = abs(l_slope) / abs(h_slope)
        if not (0.4 <= slope_ratio <= 2.5):
            return None

        upper_line = h_slope * (n - 1) + h_int
        lower_line = l_slope * (n - 1) + l_int
        channel_height = upper_line - lower_line

        if channel_height <= 0:
            return None

        if cmp <= upper_line:
            return None
        if cmp > upper_line * 1.10:
            return None

        breakout_vol_ok = cur_vol > avg_vol * 1.3

        stop_loss = upper_line * 0.97
        risk_amt = cmp - stop_loss
        if risk_amt <= 0:
            return None

        target = upper_line + channel_height
        rr = round((target - cmp) / risk_amt, 2)
        if rr < 1.0:
            return None

        return {
            "pattern":   pattern_name,
            "cmp":       cmp,
            "breakout":  round(upper_line, 2),
            "stop_loss": round(stop_loss, 2),
            "target":    round(target, 2),
            "volume":    breakout_vol_ok,
            "status":    "BREAKOUT",
            "channel_lookback_bars": lookback,
        }

    except Exception:
        return None


def detect_descending_channel(df, lookback=200, min_touches=3):
    """Catches long-term descending channels (10+ months)."""
    return _channel_breakout(df, lookback, "desc", min_touches)


def detect_ascending_channel(df, lookback=200, min_touches=3):
    """Catches stocks already trending up that break to higher highs."""
    return _channel_breakout(df, lookback, "asc", min_touches)
