"""The frozen model across many instruments, costs in basis points of price."""
import sys
sys.path.insert(0, 'research/hb')
from ict import load, unit
from exits import run as run_exits

BPS = {'eurusd': 1, 'gbpusd': 1, 'usdjpy': 1, 'audusd': 1, 'usdchf': 1, 'usdcad': 1,
       'sp500': 1, 'nasdaq': 1, 'dow': 1, 'russell': 1, 'bond30': 1, 'note10': 1,
       'gold': 2, 'silver': 2, 'copper': 2, 'platinum': 2, 'crude': 2, 'natgas': 2,
       'corn': 3, 'soybean': 3, 'dax': 2, 'nikkei': 2, 'ftse': 2, 'btc': 5, 'eth': 5}


def trades_bps(b, sigs, bps, fam='E1', cooldown=20):
    """Costs scale with price, so one figure works across gold, yen and bitcoin."""
    from exits import FAMILIES, simulate
    f = FAMILIES[fam]
    busy, out = -1, []
    for i, s in sorted(sigs):
        if i < busy:
            continue
        u = unit(b, i)
        r = simulate(b, i, s, u, f)
        if r is None:
            break
        cost_pts = b[i]['c'] * bps / 10000.0
        out.append((b[i]['t'], s, r[0] - cost_pts / (f['stop'] * u)))
        busy = i + r[1] + cooldown
    return out
