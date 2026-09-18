"""Neutral market primitives. No trading pattern is encoded here.

Every function reads bars with index <= i only. There is no FVG, no structure
break, no trend definition, no named setup — only descriptive statistics that
any hypothesis could be built out of. Which of these matter, and how, is the
policy's business, not this module's.
"""
import csv
import datetime
import statistics

MED_WIN = 100


def load(path):
    out = []
    for r in csv.DictReader(open(path)):
        out.append({'t': int(float(r['time'])), 'o': float(r['open']),
                    'h': float(r['high']), 'l': float(r['low']),
                    'c': float(r['close'])})
    return out


def _med_range(b, i, n=MED_WIN):
    seg = b[max(0, i - n + 1):i + 1]
    return statistics.median(x['h'] - x['l'] for x in seg) or 1e-9


def features(b, i):
    """Descriptive state at bar i, computed from bars <= i."""
    x = b[i]
    med = _med_range(b, i)
    rng = x['h'] - x['l']
    dt = datetime.datetime.utcfromtimestamp(x['t'])

    def net(n):
        j = max(0, i - n)
        return (x['c'] - b[j]['c']) / med

    def hi(n):
        return max(y['h'] for y in b[max(0, i - n + 1):i + 1])

    def lo(n):
        return min(y['l'] for y in b[max(0, i - n + 1):i + 1])

    rets = [(b[k]['c'] - b[k - 1]['c']) / med
            for k in range(max(1, i - 19), i + 1)]

    up = dn = 0
    for k in range(i, max(0, i - 10), -1):
        if b[k]['c'] > b[k]['o'] and dn == 0:
            up += 1
        elif b[k]['c'] < b[k]['o'] and up == 0:
            dn += 1
        else:
            break

    h20, l20, h60, l60 = hi(20), lo(20), hi(60), lo(60)
    # first bar of the current UTC day
    d0 = i
    while d0 > 0 and datetime.datetime.utcfromtimestamp(b[d0 - 1]['t']).date() == dt.date():
        d0 -= 1

    return {
        'i': i,
        'price': x['c'],
        'med': med,
        'hour': dt.hour,
        'rng': rng / med,                                  # this bar's range
        'body': abs(x['c'] - x['o']) / med,
        'pos': (x['c'] - x['l']) / rng if rng > 0 else 0.5,  # close in bar range
        'vol20': statistics.pstdev(rets) if len(rets) > 2 else 0.0,
        'net5': net(5), 'net20': net(20), 'net60': net(60),
        'span20': (h20 - l20) / med, 'span60': (h60 - l60) / med,
        'pos20': (x['c'] - l20) / (h20 - l20) if h20 > l20 else 0.5,
        'pos60': (x['c'] - l60) / (h60 - l60) if h60 > l60 else 0.5,
        'new_hi20': x['h'] >= h20, 'new_lo20': x['l'] <= l20,
        'up_streak': up, 'dn_streak': dn,
        'since_open': i - d0,
        'from_open': (x['c'] - b[d0]['o']) / med,
    }
