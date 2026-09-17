"""Four independent entry generators for HB-2.

A and B are mine; C and D are Hummingbot controller logic (bollinger_v1,
supertrend_v1) with their own default parameters, used as candidate mechanisms
only. Every generator returns {bar_index: 'LONG'|'SHORT'} and may read only
bars up to and including that index.
"""
import sys, datetime as dt
sys.path.insert(0, '/home/user/hb-compat')
sys.path.insert(0, 'research/hb')
from ict import signals as ict_signals, WARMUP


def comp_A(b):
    """Market structure + liquidity sweep with the trend (HB-1)."""
    return {i: s for i, s in ict_signals(b)}


def comp_B(b, k=0.3):
    """Daily volatility breakout: cross of day-open +/- k * previous day range."""
    day = [dt.datetime.utcfromtimestamp(x['t']).date() for x in b]
    starts, hi, lo = {}, {}, {}
    for i, d in enumerate(day):
        if d not in starts:
            starts[d] = i
        hi[d] = max(hi.get(d, -1e18), b[i]['h'])
        lo[d] = min(lo.get(d, 1e18), b[i]['l'])
    days = sorted(starts)
    prev = {days[j]: days[j - 1] for j in range(1, len(days))}
    out = {}
    for i in range(WARMUP, len(b) - 1):
        d = day[i]
        if d not in prev:
            continue
        rng = hi[prev[d]] - lo[prev[d]]
        if rng <= 0:
            continue
        o = b[starts[d]]['o']
        c, pc = b[i]['c'], b[i - 1]['c']
        if pc <= o + k * rng < c:
            out[i] = 'LONG'
        elif pc >= o - k * rng > c:
            out[i] = 'SHORT'
    return out


def _frame(b):
    import pandas as pd
    return pd.DataFrame({'open': [x['o'] for x in b], 'high': [x['h'] for x in b],
                         'low': [x['l'] for x in b], 'close': [x['c'] for x in b]})


def comp_C(b, length=100, std=2.0):
    """Hummingbot bollinger_v1 defaults: BBP < 0 -> LONG, BBP > 1 -> SHORT."""
    import pandas_ta  # noqa: F401  (registers the .ta accessor)
    bb = _frame(b).ta.bbands(length=length, std=std)
    p = bb[f'BBP_{length}_{std}']
    out = {}
    for i in range(WARMUP, len(b) - 1):
        v = p.iloc[i]
        if v != v:
            continue
        if v < 0:
            out[i] = 'LONG'
        elif v > 1:
            out[i] = 'SHORT'
    return out


def comp_D(b, length=20, mult=4.0, thr=0.01):
    """Hummingbot supertrend_v1 defaults: SUPERTd direction, price near the line."""
    import pandas_ta  # noqa: F401
    f = _frame(b)
    st = f.ta.supertrend(length=length, multiplier=mult)
    d = st[f'SUPERTd_{length}_{mult}']
    line = st[f'SUPERT_{length}_{mult}']
    out = {}
    for i in range(WARMUP, len(b) - 1):
        if d.iloc[i] != d.iloc[i]:
            continue
        c = b[i]['c']
        if abs(c - line.iloc[i]) / c > thr:
            continue                       # too far from the line: no entry
        out[i] = 'LONG' if d.iloc[i] > 0 else 'SHORT'
    return out


GENERATORS = {'A': comp_A, 'B': comp_B, 'C': comp_C, 'D': comp_D}
