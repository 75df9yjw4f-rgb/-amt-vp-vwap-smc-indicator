import sys, statistics, random, collections, datetime as dt
sys.path.insert(0, 'research/hb')
from ict import load, unit
from run_ict import simulate, K_STOP, HORIZON, COOLDOWN
from run_hb2 import stats, monthly
import smc


def trades(b, sigs, cost):
    busy, out = -1, []
    for i, s in sorted(sigs):
        if i < busy:
            continue
        u = unit(b, i)
        r = simulate(b, i, s, u)
        if r is None:
            break
        out.append((b[i]['t'], s, r[0] - cost / (K_STOP * u)))
        busy = i + r[1] + COOLDOWN
    return out


def rand_bars(b, tr, cost, runs=30):
    if not tr:
        return None
    n = len(tr); share = sum(1 for t in tr if t[1] == 'LONG') / n
    vals = []
    for s in range(runs):
        rg = random.Random(7000 + s)
        fake = []
        seen = set()
        while len(seen) < n:
            i = rg.randrange(smc.WARMUP, len(b) - HORIZON - 2)
            if i in seen:
                continue
            seen.add(i)
            fake.append((i, 'LONG' if rg.random() < share else 'SHORT'))
        vals.append(stats(trades(b, fake, cost)).get('exp', 0))
    return statistics.mean(vals)


def show(name, b, tr, cost, ctrl=True):
    s = stats(tr)
    if not s['n']:
        print(f'{name:<38} n=0')
        return s
    c = rand_bars(b, tr, cost) if ctrl else None
    mo = monthly(tr)
    tag = '' if s['n'] >= 30 else '  [UNTESTED n<30]'
    cs = f'  контроль={c:+.3f}' if c is not None else ''
    print(f"{name:<38} n={s['n']:<4} exp={s['exp']:+.3f}R  95%[{s['lo']:+.3f},{s['hi']:+.3f}]"
          f"  wr={s['wr']:.1%}  PF={s['pf']:.2f}  итог={s['tot']:+.1f}R  мес+={mo[1]:.0%}{cs}{tag}")
    return s


def main(path, cost, label):
    b = load(path)
    print(f'\n=== {label}: {len(b)} баров, {dt.datetime.utcfromtimestamp(b[0]["t"]).date()} → '
          f'{dt.datetime.utcfromtimestamp(b[-1]["t"]).date()}, издержки {cost} ===')
    full = smc.signals(b)
    res = {}
    res['full'] = show('полная модель: свип + FVG + смещение', b, trades(b, full, cost), cost)
    res['nofvg'] = show('свип + смещение, без FVG', b, trades(b, smc.signals(b, need_fvg=False), cost), cost)
    res['nobias'] = show('свип + FVG, без смещения', b, trades(b, smc.signals(b, use_bias=False), cost), cost)
    res['fvgonly'] = show('FVG в окне, без свипа', b, trades(b, smc.signals(b, need_sweep=False), cost), cost)
    res['mirror'] = show('зеркало: по направлению свипа', b, trades(b, smc.signals(b, mirror=True), cost), cost)
    tr = trades(b, full, cost)
    for side in ('LONG', 'SHORT'):
        t = [x for x in tr if x[1] == side]
        if t:
            s = stats(t)
            print(f'   полная модель {side:<5} n={s["n"]:<4} exp={s["exp"]:+.3f}R  wr={s["wr"]:.1%}')
    return res


if __name__ == '__main__':
    U = '/root/.claude/uploads/56d1edeb-f8a4-52be-94f9-383031911280/'
    for f, c, lbl in [('86675744-OANDA_XAUUSD_15.csv', 0.30, 'XAUUSD 15m'),
                      ('8cdf77f5-IG_NASDAQ_2.csv', 1.00, 'NASDAQ 15m'),
                      ('daf08717-BINANCE_BTCUSDT_2.csv', 40.0, 'BTCUSDT 15m')]:
        main(U + f, c, lbl)
