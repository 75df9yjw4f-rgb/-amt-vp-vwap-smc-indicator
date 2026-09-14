#!/usr/bin/env python3
"""
ACE — profile accuracy / load harness (P11).

Mirrors the Pine Profile Engine (fixed-step add-only grid, M1/M3 distribution,
classic pairwise Value Area) against a tick-level ground truth, so the
Lite / Standard / Pro comparison rests on measurements rather than assertions.

It does NOT touch src/ACE.pine. Run:  python3 tools/profile_sim.py
"""
import random
import statistics as st

MINTICK = 0.25          # ES-like
RANGE_ATR_MULT = 10.0   # profRangeAtr default


# ---------------------------------------------------------------- ground truth
def make_session(rng, n_bars, ticks_per_bar, start=5000.0):
    """Mean-reverting tick process, grouped into bars. Returns bars + true VAP.

    A pure random walk produces an almost flat profile, so its POC is decided by
    noise and any accuracy measured against it is meaningless. Price here is
    pulled toward a slowly drifting "value" level, which gives the session a
    genuine mode - the thing a volume profile is supposed to find.
    """
    bars, vap, px = [], {}, start
    value = start
    pull_scale = 20 * MINTICK
    for b in range(n_bars):
        # Value migrates slowly, as it does between balance areas.
        value += rng.gauss(0, 0.35) * MINTICK
        o = px
        hi, lo, vol = px, px, 0.0
        for _ in range(ticks_per_bar):
            bias = max(-0.35, min(0.35, (value - px) / pull_scale))
            px += MINTICK if rng.random() < 0.5 + bias else -MINTICK
            q = rng.randint(1, 10)
            k = round(px / MINTICK)
            vap[k] = vap.get(k, 0.0) + q
            vol += q
            hi, lo = max(hi, px), min(lo, px)
        bars.append((o, hi, lo, px, vol))
    return bars, vap


def va_classic(vols, poc_i, total, pct=70.0):
    """Identical to profVaClassic() in the Pine source."""
    n = len(vols)
    lo_i = hi_i = poc_i
    target, acc = total * pct / 100.0, vols[poc_i]
    up, dn, guard = poc_i + 1, poc_i - 1, 0
    while acc < target and (up < n or dn >= 0) and guard < n:
        guard += 1
        can_up, can_dn = up < n, dn >= 0
        v_up = (vols[up] if can_up else 0) + (vols[up + 1] if up + 1 < n else 0)
        v_dn = (vols[dn] if can_dn else 0) + (vols[dn - 1] if dn - 1 >= 0 else 0)
        if can_up and (not can_dn or v_up >= v_dn):
            acc += v_up
            hi_i = min(up + 1, n - 1)
            up += 2
        elif can_dn:
            acc += v_dn
            lo_i = max(dn - 1, 0)
            dn -= 2
        else:
            break
    return lo_i, hi_i


def truth(vap):
    keys = sorted(vap)
    vols = [vap[k] for k in keys]
    poc_i = max(range(len(vols)), key=lambda i: vols[i])
    lo_i, hi_i = va_classic(vols, poc_i, sum(vols))
    return (keys[poc_i] * MINTICK, keys[lo_i] * MINTICK, keys[hi_i] * MINTICK)


# ------------------------------------------------------------------ the engine
class Profile:
    """Fixed step, add-only, grid extended with empty bins. Never redistributed."""

    def __init__(self, center, step, bins):
        self.step, self.bins = step, bins
        self.lo = center - (bins / 2.0) * step
        self.vol = [0.0] * bins
        self.total = 0.0
        self.ops = 0

    def _idx(self, p):
        return int((p - self.lo) // self.step)

    def _extend(self, lo, hi, cap):
        if lo < self.lo:
            add = min(int((self.lo - lo) / self.step) + 1, max(0, cap - self.bins))
            if add > 0:
                self.vol = [0.0] * add + self.vol
                self.lo -= add * self.step
                self.bins += add
        top = self.lo + self.bins * self.step
        if hi >= top:
            add = min(int((hi - top) / self.step) + 1, max(0, cap - self.bins))
            if add > 0:
                self.vol += [0.0] * add
                self.bins += add

    def add_bar(self, o, h, l, c, v, model, cap, max_per_bar):
        self._extend(l, h, cap)
        i_lo, i_hi = max(0, self._idx(l)), min(self.bins - 1, self._idx(h))
        self.total += v
        if model == "M1" or i_hi < i_lo or h <= l or (i_hi - i_lo) > max_per_bar:
            i = max(0, min(self.bins - 1, self._idx(c)))
            self.vol[i] += v
            self.ops += 1
            return
        mid, half = (h + l + c) / 3.0, (h - l) / 2.0

        def weight(i):
            ov = min(self.lo + (i + 1) * self.step, h) - max(self.lo + i * self.step, l)
            if ov <= 0:
                return 0.0
            w = ov / (h - l)
            if model == "M3" and half > 0:
                bm = self.lo + (i + 0.5) * self.step
                w *= max(0.05, 1.0 - abs(bm - mid) / half)
            return w

        ws = [weight(i) for i in range(i_lo, i_hi + 1)]
        self.ops += 2 * len(ws)
        s = sum(ws)
        if s > 0:
            for k, w in enumerate(ws):
                if w > 0:
                    self.vol[i_lo + k] += v * w / s

    def finalize(self, count_ops=True):
        if self.total <= 0:
            return None
        poc_i = max(range(self.bins), key=lambda i: self.vol[i])
        lo_i, hi_i = va_classic(self.vol, poc_i, self.total)
        if count_ops:
            self.ops += 2 * self.bins
        return (self.lo + (poc_i + 0.5) * self.step,
                self.lo + lo_i * self.step,
                self.lo + (hi_i + 1) * self.step)


# As SHIPPED. Performance Mode resolves only: bins, profile count, max zones and
# the recalc cadence. It does NOT set the distribution model - that is the user's
# `Bar distribution model` input, which defaults to M3 in every mode. With the
# default `Bins = 50`, Pro resolves to 50 bins too, not 150.
MODES = {
    "Lite (pre-fix)":  (24, "M3", 0),    # 0 = last bar only: the P10 defect
    "Lite":            (24, "M3", 10),
    "Standard":        (50, "M3", 5),
    "Pro (Bins=50)":   (50, "M3", 1),
    "Pro (Bins=150)":  (150, "M3", 1),
    # Diagnostics: what the distribution model alone is worth.
    "  24 bins / M1":  (24, "M1", 10),
    "  50 bins / M1":  (50, "M1", 5),
    " 150 bins / M1":  (150, "M1", 1),
}


def run(seed, n_bars=300, ticks=60):
    rng = random.Random(seed)
    bars, vap = make_session(rng, n_bars, ticks)
    ref = truth(vap)
    atr = st.mean(h - l for _, h, l, _, _ in bars)
    out = {}
    for name, (bins, model, cadence) in MODES.items():
        step = max(MINTICK, round((atr * RANGE_ATR_MULT / bins) / MINTICK) * MINTICK)
        p = Profile(bars[0][0], step, bins)
        cap, last, stale, ready_at = min(500, bins * 4), None, [], None
        for i, (o, h, l, c, v) in enumerate(bars):
            p.add_bar(o, h, l, c, v, model, cap, 60)
            due = (i % cadence == 0) if cadence > 0 else False
            if due or i == len(bars) - 1:
                last = p.finalize()
                if ready_at is None and last:
                    ready_at = i
            exact = p.finalize(count_ops=False) if last else None   # measurement only
            if last and exact:
                stale.append(abs(last[0] - exact[0]) / p.step)
        final = last
        out[name] = dict(
            step=step, bins=p.bins, cadence=cadence, model=model,
            poc_err=abs(final[0] - ref[0]) / step,
            val_err=abs(final[1] - ref[1]) / step,
            vah_err=abs(final[2] - ref[2]) / step,
            poc_ticks=abs(final[0] - ref[0]) / MINTICK,
            stale=st.mean(stale) if stale else 0.0,
            ready_at=ready_at,
            ops=p.ops / len(bars),
        )
    return out


def main():
    runs = [run(s) for s in range(24)]
    print(f"{'mode':16} {'bins':>5} {'model':>6} {'recalc':>7} "
          f"{'POC err':>9} {'VAL err':>8} {'VAH err':>8} {'POC err':>9} "
          f"{'stale':>7} {'ready':>6} {'ops/bar':>8}")
    print(f"{'':16} {'':>5} {'':>6} {'':>7} {'(bins)':>9} {'(bins)':>8} "
          f"{'(bins)':>8} {'(ticks)':>9} {'(bins)':>7} {'(bar)':>6} {'':>8}")
    print("-" * 102)
    for name in MODES:
        rs = [r[name] for r in runs]
        m = lambda k: st.mean(r[k] for r in rs)
        print(f"{name:16} {rs[0]['bins']:>5} {rs[0]['model']:>6} "
              f"{rs[0]['cadence']:>6}b {m('poc_err'):>9.2f} {m('val_err'):>8.2f} "
              f"{m('vah_err'):>8.2f} {m('poc_ticks'):>9.2f} {m('stale'):>7.2f} "
              f"{m('ready_at'):>6.1f} {m('ops'):>8.1f}")
    print(f"\n{len(runs)} runs x 300 bars x 60 intrabar ticks, tick size {MINTICK}")
    print("Errors are vs a tick-level ground-truth profile, in BINS of that mode.")


if __name__ == "__main__":
    main()
