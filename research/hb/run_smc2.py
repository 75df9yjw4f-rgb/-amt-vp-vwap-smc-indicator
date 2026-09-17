import sys, datetime as dt
sys.path.insert(0, 'research/hb')
from ict import load
from run_smc import trades, show
from run_hb2 import stats
import smc2

U = '/root/.claude/uploads/56d1edeb-f8a4-52be-94f9-383031911280/'
FILES = [('XAUUSD 15m', '86675744-OANDA_XAUUSD_15.csv', 0.30),
         ('NASDAQ 15m', '8cdf77f5-IG_NASDAQ_2.csv', 1.00),
         ('BTCUSDT 15m', 'daf08717-BINANCE_BTCUSDT_2.csv', 40.0),
         ('XAUUSD 1H', 'ec357a9e-OANDA_XAUUSD_60.csv', 0.30)]

pool = {}
for lbl, f, c in FILES:
    b = load(U + f)
    print(f'\n=== {lbl}: {len(b)} баров, {dt.datetime.utcfromtimestamp(b[0]["t"]).date()} → '
          f'{dt.datetime.utcfromtimestamp(b[-1]["t"]).date()} ===')
    br = {'по смещению': smc2.signals(b),
          'против смещения': smc2.signals(b, counter=True),
          'без смещения': smc2.signals(b, use_bias=False),
          'по смещению + возврат 50%': smc2.signals(b, retest=True)}
    for name, sg in br.items():
        tr = trades(b, sg, c)
        show(name, b, tr, c, ctrl=(name == 'по смещению'))
        pool.setdefault(name, []).extend(tr)
    tr = trades(b, br['по смещению'], c)
    for side in ('LONG', 'SHORT'):
        t = [x for x in tr if x[1] == side]
        if t:
            s = stats(t)
            print(f'   по смещению {side:<5} n={s["n"]:<4} exp={s["exp"]:+.3f}R  wr={s["wr"]:.1%}')

print('\n=== пулом по четырём прогонам ===')
for name, tr in pool.items():
    s = stats(tr)
    print(f"{name:<28} n={s['n']:<4} exp={s['exp']:+.3f}R  95%[{s['lo']:+.3f},{s['hi']:+.3f}]"
          f"  wr={s['wr']:.1%}  PF={s['pf']:.2f}  итог={s['tot']:+.1f}R")
