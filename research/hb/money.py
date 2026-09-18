"""Convert measured R-sequences into dollars on a fixed account model.

Account: start 1000$, risk 7% of CURRENT equity per trade (compounding),
leverage cap 15x. Leverage does not change the outcome — risk per trade is
already fixed in percent — it only decides whether the required position size
is reachable. That check is reported separately.
"""
import sys, math, statistics, datetime as dt, collections
sys.path.insert(0, 'research/hb')
from ict import load, unit
from run_ict import K_STOP, HORIZON, COOLDOWN, simulate

START, RISK, LEV = 1000.0, 0.07, 15.0


def trades(b, sig, cost):
    """(timestamp, side, R, stop distance as a fraction of price)."""
    busy, out = -1, []
    for i in sorted(sig):
        if i < busy:
            continue
        u = unit(b, i)
        r = simulate(b, i, sig[i], u)
        if r is None:
            break
        stop_pts = K_STOP * u
        out.append((b[i]['t'], sig[i], r[0] - cost / stop_pts, stop_pts / b[i]['c']))
        busy = i + r[1] + COOLDOWN
    return out


def account(tr, risk=RISK, start=START, lev=None):
    """lev: cap on notional/equity. A stop so tight that 7% risk would need more
    leverage than the cap means the position is smaller, so less is risked."""
    eq, pk, dd, need = start, start, 0.0, []
    curve = []
    for _, _, r, sp in sorted(tr):
        eff = min(risk, lev * sp) if lev else risk
        eq *= (1 + eff * r)
        if eq <= 0:
            return dict(final=0.0, dd=-1.0, lev=max(need), ruin=True, n=len(tr))
        pk = max(pk, eq)
        dd = min(dd, eq / pk - 1)
        need.append(risk / sp)          # notional / equity required for this stop
        curve.append(eq)
    return dict(final=eq, dd=dd, lev=(statistics.median(need) if need else 0),
                lev_max=(max(need) if need else 0), ruin=False, n=len(tr), curve=curve)


def show(name, tr, span=None):
    a = account(tr)
    if not a['n']:
        print(f'{name:<34} нет сделок')
        return a
    mult = a['final'] / START
    flag = '' if a['lev_max'] <= LEV else f"  ПРЕВЫШЕНО плечо (нужно до {a['lev_max']:.1f}x)"
    print(f"{name:<34} n={a['n']:<4} итог=${a['final']:>10,.0f}  ×{mult:>6.2f}  "
          f"макс.просадка={a['dd']:>7.1%}  плечо~{a['lev']:.1f}x{flag}")
    return a
