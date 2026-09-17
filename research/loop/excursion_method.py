"""The method that produced the first positive out-of-sample result on 1H gold.

It is a procedure, not a rule: on a derivation slice it MEASURES where price
goes after the entry condition and how far it runs each way, then reads the
direction and the exits off those measurements. Nothing is chosen by judgement
and nothing is swept, so the same code can be pointed at another instrument and
the answer it gives is the instrument's, not mine.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import load, features   # noqa: E402
from engine import simulate, WARMUP   # noqa: E402

HORIZON = 20


def entries(b, lo=WARMUP, hi=None):
    """Compression: the entry condition of the strategy being improved."""
    hi = hi if hi is not None else len(b) - HORIZON - 1
    for i in range(lo, hi):
        f = features(b, i)
        if f['rng'] < 0.5 and f['span20'] < 4:
            yield i


def med_range(b, i, w=500):
    return statistics.median(x['h'] - x['l'] for x in b[max(0, i - w + 1):i + 1])


def derive(b):
    """Read direction and exits off the derivation slice. No judgement, no sweep."""
    up, dn = [], []
    for i in entries(b):
        m = med_range(b, i)
        seg = b[i + 1:i + HORIZON + 1]
        if len(seg) < HORIZON:
            continue
        e = b[i]['c']
        up.append(max(x['h'] - e for x in seg) / m)
        dn.append(max(e - x['l'] for x in seg) / m)
    if len(up) < 15:
        return None
    mu, md = statistics.mean(up), statistics.mean(dn)
    side = 'LONG' if mu > md else 'SHORT'
    fav, adv = (mu, md) if side == 'LONG' else (md, mu)
    rnd = lambda v: max(1.0, round(v * 2) / 2)      # to the nearest 0.5
    return {'n': len(up), 'mfe_up': round(mu, 2), 'mae_dn': round(md, 2),
            'side': side, 'k_stop': rnd(adv), 'k_target': rnd(fav)}


def test(b, d, flip=False):
    side = d['side']
    if flip:
        side = 'SHORT' if side == 'LONG' else 'LONG'
    ex = {"k_med": 2.0, "med_window": 500, "exit_after": HORIZON,
          "k_stop": d['k_stop'], "k_target": d['k_target'], "cooldown": 20}
    busy, rs = -1, []
    for i in entries(b):
        if i < busy:
            continue
        o = simulate(b, i, side, ex)
        if o is None:
            break
        rs.append(o['r'])
        busy = i + o['bars'] + ex['cooldown']
    return rs
