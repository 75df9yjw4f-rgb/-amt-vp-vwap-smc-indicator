"""SMC top-down: daily structure sets the side, lower timeframe gives the entry.

No session anchoring this time — that was SMC-1 and it did not survive. Here the
only claim is the one the videos make in general form: read structure on the
daily, then drop to the lower timeframe and enter on ITS structure.

Entry structure, formalised: after the daily bias is UP, the lower timeframe must
first complete a pullback (its last confirmed swing is a LOW), and then close
back above the last confirmed swing HIGH. That close is the structure shift.
Mirror for DOWN. Every swing is confirmed SWING bars late, so the level being
broken was public before the break.
"""
from smc import daily_bias, et

SWING = 3
WARMUP = 300
RETEST_WITHIN = 8      # bars allowed for the 50% pullback variant


def swings(b):
    hi, lo = [], []
    for k in range(SWING, len(b) - SWING):
        w = b[k - SWING:k + SWING + 1]
        if b[k]['h'] == max(x['h'] for x in w):
            hi.append((k + SWING, b[k]['h']))
        if b[k]['l'] == min(x['l'] for x in w):
            lo.append((k + SWING, b[k]['l']))
    return hi, lo


def shifts(b):
    """Yields (i, side, level, opposite) — a structure shift on the lower timeframe."""
    hi, lo = swings(b)
    ih = il = 0
    lastH = lastL = None
    for i in range(WARMUP, len(b) - 1):
        while ih < len(hi) and hi[ih][0] < i:
            lastH = hi[ih]; ih += 1
        while il < len(lo) and lo[il][0] < i:
            lastL = lo[il]; il += 1
        if lastH is None or lastL is None:
            continue
        c, pc = b[i]['c'], b[i - 1]['c']
        if lastL[0] > lastH[0] and c > lastH[1] >= pc:
            yield i, 'LONG', lastH[1], lastL[1]        # pullback done, break up
        elif lastH[0] > lastL[0] and c < lastL[1] <= pc:
            yield i, 'SHORT', lastL[1], lastH[1]       # pullback done, break down


def signals(b, use_bias=True, counter=False, retest=False):
    bias = daily_bias(b)
    out = []
    for i, side, lvl, opp in shifts(b):
        if use_bias:
            want = bias.get(et(b[i]['t']).date(), 'NONE')
            if want == 'NONE':
                continue
            agree = (want == 'UP') == (side == 'LONG')
            if agree == counter:
                continue
        if retest:
            mid = (lvl + opp) / 2.0
            j = None
            for k in range(i + 1, min(i + 1 + RETEST_WITHIN, len(b) - 1)):
                if (b[k]['l'] <= mid) if side == 'LONG' else (b[k]['h'] >= mid):
                    j = k
                    break
            if j is None:
                continue
            out.append((j, side))
        else:
            out.append((i, side))
    return out
