"""Medium-term long/flat strategy, designed through the TradingAgents role split.

The roles are used as a discipline for stating the case, not as a source of
truth: whatever the bull and the bear say, the verdict comes from the measurement
and its controls. The design deliberately drops the one thing docs/39 already
falsified — the short side, which was pure loss across four correlated risk
assets in a rising period.

Daily bars are aggregated from the intraday files. Every value a decision reads
is closed strictly before the decision bar.
"""
import datetime as dt
import statistics


def to_daily(b):
    """UTC-daily OHLC from intraday bars."""
    out, cur, day = [], None, None
    for x in b:
        d = dt.datetime.utcfromtimestamp(x['t']).date()
        if d != day:
            if cur:
                out.append(cur)
            cur = {'t': x['t'], 'd': d, 'o': x['o'], 'h': x['h'], 'l': x['l'], 'c': x['c']}
            day = d
        else:
            cur['h'] = max(cur['h'], x['h']); cur['l'] = min(cur['l'], x['l']); cur['c'] = x['c']
    if cur:
        out.append(cur)
    return out


def sma(c, i, n):
    return sum(c[i - n + 1:i + 1]) / n if i >= n - 1 else None


def realised_vol(c, i, n=60):
    if i < n:
        return None
    r = [c[k] / c[k - 1] - 1 for k in range(i - n + 1, i + 1)]
    return statistics.stdev(r) if len(r) > 1 else None


def exposure(d, rule, review=21, sma_n=200, mom_n=63, vol_target=None, vol_n=60):
    """Exposure per day in [0, 1+]. Decisions are taken only on review days and
    use data up to and including the previous close."""
    c = [x['c'] for x in d]
    e = [0.0] * len(d)
    warm = max(sma_n, mom_n, vol_n) + 1
    cur = 0.0
    for i in range(len(d)):
        if i < warm:
            e[i] = 0.0
            continue
        if (i - warm) % review == 0:
            j = i - 1                                 # yesterday's close decides today
            if rule == 'hold':
                on = True
            elif rule == 'sma':
                on = c[j] > sma(c, j, sma_n)
            elif rule == 'mom':
                on = c[j] / c[j - mom_n] - 1 > 0
            elif rule == 'both':
                on = c[j] > sma(c, j, sma_n) and c[j] / c[j - mom_n] - 1 > 0
            elif rule == 'either':
                on = c[j] > sma(c, j, sma_n) or c[j] / c[j - mom_n] - 1 > 0
            else:
                raise ValueError(rule)
            cur = 1.0 if on else 0.0
            if cur and vol_target:
                v = realised_vol(c, j, vol_n)
                if v:
                    cur = min(1.5, vol_target / (v * (252 ** 0.5)))
        e[i] = cur
    return e


def equity(d, e, cost_bps=5.0, start=1000.0):
    """Costs are charged on every change of exposure, in basis points of turnover."""
    c = [x['c'] for x in d]
    eq, pk, dd = start, start, 0.0
    curve, prev = [], 0.0
    for i in range(1, len(d)):
        eq *= 1 + e[i - 1] * (c[i] / c[i - 1] - 1)
        turn = abs(e[i] - prev)
        if turn:
            eq *= 1 - turn * cost_bps / 10000.0
        prev = e[i]
        pk = max(pk, eq); dd = min(dd, eq / pk - 1)
        curve.append(eq)
    return eq, dd, curve


def stats(d, e, **kw):
    fin, dd, curve = equity(d, e, **kw)
    yrs = (d[-1]['d'] - d[0]['d']).days / 365.25
    cagr = (fin / 1000.0) ** (1 / yrs) - 1 if yrs > 0 and fin > 0 else -1
    tim = sum(1 for x in e if x > 0) / len(e)
    return dict(final=fin, dd=dd, cagr=cagr, years=yrs, time_in=tim,
                mar=(cagr / -dd if dd else float('inf')))
