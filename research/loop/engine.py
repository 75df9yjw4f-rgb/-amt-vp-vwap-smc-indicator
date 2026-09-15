"""Walk-forward engine. Enforces the barrier structurally.

`features(bars[:i+1], i)` is handed a SLICE, so bar i+1 does not exist for the
decision at all — not "is not read", but is not present. The outcome is computed
only after the decision has been hashed into the ledger.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from features import load, features            # noqa: E402
from ledger import Ledger                       # noqa: E402
from policy import load_all, active_at          # noqa: E402

WARMUP = 120


def simulate(b, i, side, ex):
    """Pessimistic: if stop and target are both touched on a bar, the stop wins."""
    e = b[i]['c']
    sgn = 1 if side == 'LONG' else -1
    stop = e - sgn * e * ex['sl_pct'] / 100.0
    target = e + sgn * e * ex['tp_pct'] / 100.0
    risk = abs(e - stop)
    mfe = mae = 0.0
    for k in range(1, ex['max_bars'] + 1):
        j = i + k
        if j >= len(b):
            return None
        x = b[j]
        fav = (x['h'] - e) if side == 'LONG' else (e - x['l'])
        adv = (e - x['l']) if side == 'LONG' else (x['h'] - e)
        mfe, mae = max(mfe, fav / risk), max(mae, adv / risk)
        hs = (x['l'] <= stop) if side == 'LONG' else (x['h'] >= stop)
        ht = (x['h'] >= target) if side == 'LONG' else (x['l'] <= target)
        if hs:
            return dict(r=-1.0, bars=k, outcome='STOP', mfe=round(mfe, 3),
                        mae=round(mae, 3), exit_price=round(stop, 3))
        if ht:
            return dict(r=1.0, bars=k, outcome='TARGET', mfe=round(mfe, 3),
                        mae=round(mae, 3), exit_price=round(target, 3))
    x = b[i + ex['max_bars']]
    rm = ((x['c'] - e) if side == 'LONG' else (e - x['c'])) / risk
    return dict(r=round(rm, 3), bars=ex['max_bars'], outcome='TIME',
                mfe=round(mfe, 3), mae=round(mae, 3), exit_price=x['c'])


def run(bars_path, policy_dir, ledger_path, stop_after_trades=None, verbose=True):
    b = load(bars_path)
    policies = load_all(policy_dir)
    led = Ledger(ledger_path)

    done = {d['bar'] for d in led.decisions()}
    outcomes = {o['decision_hash'] for o in led.outcomes()}
    taken = [o for o in led.outcomes()]
    busy_until = -1
    for o in taken:
        busy_until = max(busy_until, o['bar'] + o['bars'] + o['cooldown'])
    start = max(WARMUP, (max(done) + 1) if done else WARMUP)

    made = 0
    for i in range(start, len(b)):
        if i < busy_until:
            continue
        pol = active_at(policies, i)
        # --- BARRIER: a slice, so the future is not merely unread but absent ---
        f = features(b[:i + 1], i)
        action, rule_id = pol.decide(f)
        dec = {'bar': i, 'time': b[i]['t'], 'policy_version': pol.version,
               'action': action, 'rule_id': rule_id,
               'features': {k: (round(v, 4) if isinstance(v, float) else v)
                            for k, v in f.items()},
               'exits': pol.exits, 'decided_by': 'policy(claude)'}
        rec = led.append('DECISION', dec)
        # --- everything below may look at the future; the decision is sealed ---
        if action == 'HOLD':
            continue
        o = simulate(b, i, action, pol.exits)
        if o is None:
            break
        o.update({'bar': i, 'decision_hash': rec['hash'], 'side': action,
                  'entry_price': b[i]['c'], 'cooldown': pol.exits['cooldown'],
                  'policy_version': pol.version, 'rule_id': rule_id})
        led.append('OUTCOME', o)
        busy_until = i + o['bars'] + pol.exits['cooldown']
        made += 1
        if verbose:
            print(f"  бар {i:5d} v{pol.version} {action:<5s} [{rule_id}] "
                  f"{o['outcome']:<6s} {o['r']:+.1f}R")
        if stop_after_trades and made >= stop_after_trades:
            break
    return made
