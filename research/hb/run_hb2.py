"""HB-2: combining strategies, on one instrument, with controls.

Branches: each component alone, every pairwise confluence, the equal-weight
portfolio. Exits, costs, cooldown and bars are identical everywhere, so the only
difference between branches is which bars they enter on.
"""
import sys, math, random, statistics, datetime as dt, collections
sys.path.insert(0, 'research/hb')
from ict import load, unit, WARMUP
from run_ict import simulate, K_STOP, HORIZON, COOLDOWN
from components import GENERATORS

CONFLUENCE_W = 5        # bars; registered before the run


def sequential(b, sig, cost, rand=False, seed=0):
    """Take signals in order, one position at a time, cooldown after exit."""
    rg = random.Random(seed)
    busy, out = -1, []
    for i in sorted(sig):
        if i < busy:
            continue
        u = unit(b, i)
        side = rg.choice(['LONG', 'SHORT']) if rand else sig[i]
        r = simulate(b, i, side, u)
        if r is None:
            break
        out.append((b[i]['t'], side, r[0] - cost / (K_STOP * u)))
        busy = i + r[1] + COOLDOWN
    return out


def confluence(x, y, w=CONFLUENCE_W):
    """x fires at i and y agreed at or within w bars before i (or vice versa)."""
    out = {}
    for src, other in ((x, y), (y, x)):
        for i, s in src.items():
            for j in range(i - w, i + 1):
                if other.get(j) == s:
                    out[i] = s
                    break
    return out


def stats(tr):
    if not tr:
        return dict(n=0)
    r = [t[2] for t in tr]
    n, m = len(r), statistics.mean(r)
    sd = statistics.stdev(r) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    g = sum(x for x in r if x > 0); l = -sum(x for x in r if x < 0)
    eq, pk, dd = 0.0, 0.0, 0.0
    for x in r:
        eq += x; pk = max(pk, eq); dd = min(dd, eq - pk)
    return dict(n=n, exp=m, wr=sum(1 for x in r if x > 0) / n, tot=sum(r),
                pf=(g / l if l else float('inf')), dd=dd,
                lo=m - 1.96 * se, hi=m + 1.96 * se)


def monthly(tr):
    m = collections.defaultdict(float)
    for t, _, r in tr:
        d = dt.datetime.utcfromtimestamp(t)
        m[f'{d.year}-{d.month:02d}'] += r
    v = list(m.values())
    return len(v), (sum(1 for x in v if x > 0) / len(v) if v else 0), \
        (statistics.median(v) if v else 0)


def line(name, tr, ctrl=None):
    s = stats(tr)
    if not s['n']:
        return f'{name:<26} n=0'
    mo = monthly(tr)
    tag = '' if s['n'] >= 30 else '  [UNTESTED n<30]'
    c = f"  ctrl={ctrl:+.3f}" if ctrl is not None else ''
    return (f"{name:<26} n={s['n']:<4} exp={s['exp']:+.3f}R  95%[{s['lo']:+.3f},{s['hi']:+.3f}]"
            f"  wr={s['wr']:.1%}  PF={s['pf']:.2f}  tot={s['tot']:+.1f}R  dd={s['dd']:.1f}R"
            f"  мес+={mo[1]:.0%}({mo[0]}){c}{tag}")


def control(b, sig, cost, runs=30):
    v = [stats(sequential(b, sig, cost, rand=True, seed=s)).get('exp', 0) for s in range(runs)]
    return statistics.mean(v)


def control_bars(b, tr, cost, runs=30):
    """Same number of entries, random bars, same long share: isolates drift."""
    if not tr:
        return None
    n = len(tr)
    share = sum(1 for t in tr if t[1] == 'LONG') / n
    lo, hi = WARMUP, len(b) - HORIZON - 2
    out = []
    for s in range(runs):
        rg = random.Random(1000 + s)
        fake = {}
        while len(fake) < n:
            i = rg.randrange(lo, hi)
            fake[i] = 'LONG' if rg.random() < share else 'SHORT'
        out.append(stats(sequential(b, fake, cost)).get('exp', 0))
    return statistics.mean(out)


def main(path, cost):
    b = load(path)
    print(f'{len(b)} баров, {dt.datetime.utcfromtimestamp(b[0]["t"]).date()} → '
          f'{dt.datetime.utcfromtimestamp(b[-1]["t"]).date()}, издержки {cost} пункта\n')
    sig = {k: g(b) for k, g in GENERATORS.items()}
    print('сигналов до кулдауна: ' + ', '.join(f'{k}={len(v)}' for k, v in sig.items()) + '\n')

    single = {}
    print('--- компоненты по отдельности ---')
    for k in 'ABCD':
        tr = sequential(b, sig[k], cost)
        single[k] = tr
        print(line(k, tr, control(b, sig[k], cost)))
        cb = control_bars(b, tr, cost)
        if cb is not None:
            print(f'   контроль «случайные бары, та же доля LONG»: {cb:+.3f}R')

    print('\n--- конфлюэнс (пары, согласие направления в окне 5 баров) ---')
    conf = {}
    for i, x in enumerate('ABCD'):
        for y in 'ABCD'[i + 1:]:
            s = confluence(sig[x], sig[y])
            tr = sequential(b, s, cost)
            conf[x + y] = tr
            print(line(x + '+' + y, tr, control(b, s, cost) if s else None))

    print('\n--- портфель (компоненты торгуют независимо, доходности складываются) ---')
    pool = sorted([t for k in 'ABCD' for t in single[k]])
    print(line('портфель A+B+C+D', pool))
    for k in 'ABCD':
        s = stats(single[k])
        if s['n']:
            print(f"   компонент {k}: dd={s['dd']:.1f}R  мес+={monthly(single[k])[1]:.0%}")

    print('\n--- сторона сделки ---')
    for k in 'ABCD':
        for side in ('LONG', 'SHORT'):
            t = [x for x in single[k] if x[1] == side]
            if t:
                s = stats(t)
                print(f'{k} {side:<5} n={s["n"]:<4} exp={s["exp"]:+.3f}R  wr={s["wr"]:.1%}')

    best_single = max((stats(v).get('exp', -9), k) for k, v in single.items() if stats(v)['n'] >= 30)
    ok = [(stats(v)['exp'], k) for k, v in conf.items() if stats(v)['n'] >= 30]
    print('\n--- проверка предсказания ---')
    print(f'лучший одиночный (n>=30): {best_single[1]} {best_single[0]:+.3f}R')
    if ok:
        bc = max(ok)
        print(f'лучший конфлюэнс (n>=30): {bc[1]} {bc[0]:+.3f}R  '
              f'разница {bc[0]-best_single[0]:+.3f}R  '
              f'→ предсказание {"ОПРОВЕРГНУТО" if bc[0]-best_single[0] > 0.05 else "подтверждено"}')
    else:
        print('ни одна конфлюэнс-ветка не набрала n>=30 → предсказание НЕ ПРОВЕРЕНО')


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]))
