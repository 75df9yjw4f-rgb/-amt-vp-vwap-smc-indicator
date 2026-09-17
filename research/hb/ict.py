"""Market structure + liquidity sweep, formalised mechanically.

ICT and CRT have no canonical definitions, so the formalisation below is a
declared degree of freedom, written into the ledger before any test. Every value
it reads is available at the bar it acts on: a swing is only confirmed five bars
after it forms, so the level a sweep trades against was already public.
"""
import statistics

SWING = 5          # bars each side of a fractal; frozen before testing
WARMUP = 300


def load(path):
    import csv
    return [{'t': int(float(r['time'])), 'o': float(r['open']), 'h': float(r['high']),
             'l': float(r['low']), 'c': float(r['close'])} for r in csv.DictReader(open(path))]


def swings(b):
    """Confirmed swing points. Index k is confirmed at bar k+SWING, not before."""
    hi, lo = [], []
    for k in range(SWING, len(b) - SWING):
        w = b[k - SWING:k + SWING + 1]
        if b[k]['h'] == max(x['h'] for x in w):
            hi.append((k + SWING, k, b[k]['h']))      # (confirmed_at, at, price)
        if b[k]['l'] == min(x['l'] for x in w):
            lo.append((k + SWING, k, b[k]['l']))
    return hi, lo


def state_at(hi, lo, i):
    """Structure and the live levels, using only swings confirmed strictly before i."""
    H = [x for x in hi if x[0] < i]
    L = [x for x in lo if x[0] < i]
    if len(H) < 2 or len(L) < 2:
        return None, None, None
    trend = 'UP' if (H[-1][2] > H[-2][2] and L[-1][2] > L[-2][2]) else \
            ('DOWN' if (H[-1][2] < H[-2][2] and L[-1][2] < L[-2][2]) else 'NONE')
    return trend, H[-1][2], L[-1][2]


def signals(b, mirror=False):
    """Yields (i, side). A sweep pierces a level and closes back through it."""
    hi, lo = swings(b)
    for i in range(WARMUP, len(b) - 1):
        trend, last_hi, last_lo = state_at(hi, lo, i)
        if trend is None or trend == 'NONE':
            continue
        swept_low = b[i]['l'] < last_lo <= b[i]['c']
        swept_high = b[i]['h'] > last_hi >= b[i]['c']
        want_long = (trend == 'UP') if not mirror else (trend == 'DOWN')
        if swept_low and want_long:
            yield i, 'LONG'
        elif swept_high and not want_long:
            yield i, 'SHORT'


def unit(b, i, w=500):
    return statistics.median(x['h'] - x['l'] for x in b[max(0, i - w + 1):i + 1]) or 1e-9
