"""Equal-weight and risk-weighted portfolios across many assets, with overlays.

Weights for day i are computed from data up to day i-1 and applied to day i's
return, so no decision reads the bar it acts on.
"""
import statistics
import sys
sys.path.insert(0, 'research/hb')
from midterm import to_daily

REVIEW = 21


def trading_days(series, start=None):
    """Dates on which at least half the already-started universe has a price.

    A union of calendars silently changes the portfolio: crypto trades at the
    weekend, so on a Saturday the only available instrument gets weight 1.0 and
    the "portfolio" is one coin. That is what this rule exists to prevent.
    """
    first = {n: min(d) for n, (d, _) in series.items()}
    alld = sorted(set().union(*[set(d) for d, _ in series.values()]))
    out = []
    for day in alld:
        if start and day < start:
            continue
        started = sum(1 for n in series if first[n] <= day)
        have = sum(1 for n, (d, _) in series.items() if day in d)
        if started and have >= started / 2:
            out.append(day)
    return out


def rsi(c, i, n=14):
    if i < n:
        return None
    up = dn = 0.0
    for k in range(i - n + 1, i + 1):
        d = c[k] - c[k - 1]
        up += max(d, 0.0); dn += max(-d, 0.0)
    if dn == 0:
        return 100.0
    rs = (up / n) / (dn / n)
    return 100 - 100 / (1 + rs)


def vol(c, i, n=60):
    if i < n:
        return None
    r = [c[k] / c[k - 1] - 1 for k in range(i - n + 1, i + 1)]
    return statistics.stdev(r) or None


def sma(c, i, n=200):
    return sum(c[i - n + 1:i + 1]) / n if i >= n - 1 else None


def weights(series, day, variant, warm=201):
    """series: {name: (dates, closes)}; day: index into the common calendar.

    An instrument whose price touched zero or below anywhere in the windows a
    weight is computed from is unavailable: neither volatility nor a moving
    average means anything across a sign change (WTI, 2020-04-20)."""
    w = {}
    for name, (d, c) in series.items():
        i = d.get(day)
        if i is None or i < warm:
            continue
        if min(c[i - warm + 1:i + 1]) <= 0:
            continue
        j = i - 1                                  # yesterday decides today
        v = vol(c, j); r = rsi(c, j); s = sma(c, j)
        if v is None or r is None or s is None:
            continue
        if variant == 'V0':
            x = 1.0
        else:
            x = 1.0 / v
        if variant in ('V2', 'V5') and x:
            x *= 1.5 if r < 30 else (0.5 if r > 70 else 1.0)
        if variant == 'V3' and r > 70:
            x = 0.0
        if variant in ('V4', 'V5') and c[j] <= s:
            x = 0.0
        w[name] = x
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()} if tot else {}


def backtest(series, calendar, variant, cost_bps=2.0, start=1000.0):
    eq, pk, dd = start, start, 0.0
    cur, curve = {}, []
    for n, day in enumerate(calendar):
        if n == 0:
            continue
        if (n - 1) % REVIEW == 0:
            new = weights(series, day, variant)
            turn = sum(abs(new.get(k, 0) - cur.get(k, 0)) for k in set(new) | set(cur))
            eq *= 1 - turn * cost_bps / 10000.0
            cur = new
        step = 0.0
        for name, wgt in cur.items():
            d, c = series[name]
            i = d.get(day); p = d.get(calendar[n - 1])
            if i is None or p is None or c[p] <= 0:
                continue
            # a price crossing to zero or below wipes the leg; -306% is not a
            # return anyone realises, a total loss of the leg is
            step += wgt * (-1.0 if c[i] <= 0 else max(-1.0, c[i] / c[p] - 1))
        eq *= 1 + step
        pk = max(pk, eq); dd = min(dd, eq / pk - 1)
        curve.append((day, eq))
    return eq, dd, curve
