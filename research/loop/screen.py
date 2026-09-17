"""Sign-portability screen.

For every descriptor, split at a threshold taken from ONE segment and never
retuned, then ask a single question on every other segment: does the effect
keep its sign? A descriptor that flips is not a regime signal, however large it
looks where it was found.

This exists because the first three candidates found on SEG-5 all reversed on
3m data — and they were mutually correlated, so they were one finding, not
three. A screen is harder to fool than eyeballing a table.
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import load    # noqa: E402
from regime import regime    # noqa: E402

SRC = []   # очищено: сегментов нового эксперимента ещё нет
MIN_SIDE = 8


def collect():
    out = {}
    for nm, bars, led in SRC:
        b = load(bars)
        recs = [json.loads(l) for l in open('research/loop/state/' + led)]
        d = {r['hash']: r['payload'] for r in recs if r['kind'] == 'DECISION'}
        rows = []
        for o in [r['payload'] for r in recs if r['kind'] == 'OUTCOME']:
            g = regime(b, o['bar'])
            if g is None:
                continue
            f = dict(d[o['decision_hash']]['features'])
            f.update(g)
            rows.append((f, o['r']))
        out[nm] = rows
    return out


def main():
    D = collect()
    ref = D['SEG-5']
    keys = [k for k in ref[0][0] if isinstance(ref[0][0][k], (int, float))
            and k not in ('i', 'price', 'med')]
    res = []
    for k in keys:
        vals = [f[k] for f, _ in ref]
        if len(set(vals)) < 4:
            continue
        th = statistics.median(vals)
        diffs, ns = {}, {}
        for nm, _, _ in SRC:
            lo = [r for f, r in D[nm] if f[k] <= th]
            hi = [r for f, r in D[nm] if f[k] > th]
            if len(lo) < MIN_SIDE or len(hi) < MIN_SIDE:
                diffs[nm] = None
                continue
            diffs[nm] = statistics.mean(hi) - statistics.mean(lo)
            ns[nm] = (len(lo), len(hi))
        got = [v for v in diffs.values() if v is not None]
        if len(got) < 3:
            continue
        same = all(v > 0 for v in got) or all(v < 0 for v in got)
        res.append((same, len(got), min(abs(v) for v in got), k, th, diffs))
    res.sort(key=lambda r: (-r[0], -r[2]))
    print(f"{'признак':<12s} {'порог':>8s} " + " ".join(f"{nm:>9s}" for nm, _, _ in SRC) + "  вердикт")
    for same, ngot, _, k, th, diffs in res:
        cells = " ".join((f"{diffs[nm]:>+9.3f}" if diffs[nm] is not None else f"{'—':>9s}")
                         for nm, _, _ in SRC)
        print(f"{k:<12s} {th:>8.3f} {cells}  "
              f"{'ЗНАК УСТОЙЧИВ на '+str(ngot) if same else 'знак меняется'}")


if __name__ == '__main__':
    main()
