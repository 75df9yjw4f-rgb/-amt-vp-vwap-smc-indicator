"""Smart Money Concepts, formalised from the five uploaded videos.

What the videos actually say, stripped of vocabulary:

  * top-down bias: daily structure (higher high + higher low / lower high +
    lower low) decides the side;
  * a session level is the liquidity: the 08:00 ET hourly candle's high and low;
  * the move that matters is a SWEEP of that level followed by a close back
    through it (the "manipulation" phase);
  * entry is not the sweep itself but the imbalance (FVG) that forms after it,
    on the close of the candle that completes the gap.

Deviation declared before testing: the videos work on M1/M5. The finest data in
this project is M15, so every leg is measured on M15. This can only blunt the
model, never flatter it, but it means a null result does not refute the M1
version.
"""
import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
SWING_D = 2          # days each side for a daily fractal; confirmed 2 days late
ANCHOR_HOUR = 8      # the "8am candle" in ET
WIN_START, WIN_END = 9, 11   # ET hours in which the sweep may happen
FVG_WITHIN = 4       # bars after the sweep in which the imbalance must complete
WARMUP = 300


def et(ts):
    return dt.datetime.fromtimestamp(ts, ET)


def daily(b):
    """Daily OHLC built from the intraday bars, keyed by ET date."""
    out = {}
    for x in b:
        d = et(x['t']).date()
        o = out.get(d)
        if o is None:
            out[d] = {'o': x['o'], 'h': x['h'], 'l': x['l'], 'c': x['c']}
        else:
            o['h'] = max(o['h'], x['h']); o['l'] = min(o['l'], x['l']); o['c'] = x['c']
    return out


def daily_bias(b):
    """{ET date: 'UP'|'DOWN'|'NONE'} using only days strictly before that date."""
    d = daily(b)
    days = sorted(d)
    hi, lo = [], []
    for k in range(SWING_D, len(days) - SWING_D):
        w = days[k - SWING_D:k + SWING_D + 1]
        if d[days[k]]['h'] == max(d[x]['h'] for x in w):
            hi.append((days[k + SWING_D], d[days[k]]['h']))   # confirmed on this day
        if d[days[k]]['l'] == min(d[x]['l'] for x in w):
            lo.append((days[k + SWING_D], d[days[k]]['l']))
    out = {}
    for day in days:
        H = [x[1] for x in hi if x[0] < day]
        L = [x[1] for x in lo if x[0] < day]
        if len(H) < 2 or len(L) < 2:
            out[day] = 'NONE'
        elif H[-1] > H[-2] and L[-1] > L[-2]:
            out[day] = 'UP'
        elif H[-1] < H[-2] and L[-1] < L[-2]:
            out[day] = 'DOWN'
        else:
            out[day] = 'NONE'
    return out


def anchor_levels(b):
    """{ET date: (high, low)} of the 08:00 ET hour, and the index it closes at."""
    lv = {}
    for i, x in enumerate(b):
        t = et(x['t'])
        if t.hour == ANCHOR_HOUR:
            d = t.date()
            h, l, _ = lv.get(d, (-1e18, 1e18, -1))
            lv[d] = (max(h, x['h']), min(l, x['l']), i)
    return lv


def signals(b, use_bias=True, need_sweep=True, need_fvg=True, mirror=False):
    """Yields (i, side). Every value read is closed at or before bar i."""
    bias = daily_bias(b)
    lv = anchor_levels(b)
    out = []
    for i in range(WARMUP, len(b) - 1):
        t = et(b[i]['t'])
        if not (WIN_START <= t.hour < WIN_END):
            continue
        a = lv.get(t.date())
        if a is None or a[2] >= i:
            continue
        hi, lo = a[0], a[1]
        swept_lo = b[i]['l'] < lo <= b[i]['c']
        swept_hi = b[i]['h'] > hi >= b[i]['c']
        if need_sweep and not (swept_lo or swept_hi):
            continue
        side = ('LONG' if swept_lo else 'SHORT') if need_sweep else None
        if mirror and side:
            side = 'SHORT' if side == 'LONG' else 'LONG'
        if need_fvg:
            j = fvg_after(b, i, side)
            if j is None:
                continue
            k, fside = j
            side = side or fside
            i2 = k
        else:
            i2 = i
        if side is None:
            continue
        if use_bias:
            want = bias.get(et(b[i2]['t']).date(), 'NONE')
            if want == 'NONE' or (want == 'UP') != (side == 'LONG'):
                continue
        out.append((i2, side))
    return out


def fvg_after(b, i, side):
    """First 3-bar imbalance completing within FVG_WITHIN bars after i."""
    for k in range(i + 2, min(i + 2 + FVG_WITHIN, len(b) - 1)):
        up = b[k]['l'] > b[k - 2]['h']
        dn = b[k]['h'] < b[k - 2]['l']
        if side in (None, 'LONG') and up:
            return k, 'LONG'
        if side in (None, 'SHORT') and dn:
            return k, 'SHORT'
    return None
