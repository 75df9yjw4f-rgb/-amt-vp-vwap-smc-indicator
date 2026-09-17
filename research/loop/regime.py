"""Backward-looking regime descriptors. Every value at bar i uses bars <= i only.

These are not entry signals — they describe the market the trade is taken in.
The question they exist to answer is why the same rules gave +27.4R on one
stretch and -18.0R on another.
"""
import statistics


def regime(b, i, win=500):
    lo = max(0, i - win + 1)
    seg = b[lo:i + 1]
    if len(seg) < 100:
        return None
    rng = [x['h'] - x['l'] for x in seg]
    med = statistics.median(rng) or 1e-9
    rets = [seg[k]['c'] - seg[k - 1]['c'] for k in range(1, len(seg))]
    px = seg[-1]['c']
    denom = sum(abs(r) for r in rets) or 1e-9
    m = statistics.mean(rets)
    x1, y1 = rets[:-1], rets[1:]
    sx, sy = statistics.pstdev(x1) or 1e-9, statistics.pstdev(y1) or 1e-9
    ac = sum((p - m) * (q - m) for p, q in zip(x1, y1)) / (sx * sy * len(x1))
    # how far the window travelled against how much it moved: directionality
    eff = abs(seg[-1]['c'] - seg[0]['c']) / denom
    # what share of bars are unusually wide / unusually narrow
    exp_ = sum(1 for r in rng if r > 2 * med) / len(rng)
    comp = sum(1 for r in rng if r < 0.5 * med) / len(rng)
    # is volatility itself rising or falling across the window
    h = len(rng) // 2
    vshift = (statistics.median(rng[h:]) or 1e-9) / (statistics.median(rng[:h]) or 1e-9)
    return {
        'r_vol': 100 * med / px,          # typical bar range as % of price
        'r_eff': eff,                     # directionality of the window
        'r_ac1': ac,                      # return autocorrelation
        'r_exp': exp_,                    # share of expansion bars
        'r_comp': comp,                   # share of compression bars
        'r_vshift': vshift,               # volatility trend inside the window
        'r_drift': 100 * (seg[-1]['c'] - seg[0]['c']) / seg[0]['c'],
    }
