"""Beliefs update mechanically, not rhetorically.

A belief owns a scope expression over entry features and a prediction. Its
status is recomputed from the closed trades that fall inside its scope, using
thresholds frozen here before the run. Claude writes the belief; the arithmetic
decides whether it still stands.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from policy import ALLOWED   # noqa: E402

MIN_N = 8          # below this a belief stays UNTESTED, whatever the record
BREAKEVEN = 0.50   # 1:1 bracket
WEAK = 0.35


def status_for(n, wins):
    if n < MIN_N:
        return 'UNTESTED'
    wr = wins / n
    if wr >= BREAKEVEN:
        return 'HELD'
    if wr >= WEAK:
        return 'WEAKENED'
    return 'REJECTED'


def evaluate(beliefs, outcomes, decisions):
    by_hash = {d_hash: d for d_hash, d in decisions.items()}
    out = []
    for bl in beliefs:
        code = compile(bl['scope'], f"<belief {bl['id']}>", 'eval')
        n = wins = 0
        rs = []
        for o in outcomes:
            d = by_hash.get(o['decision_hash'])
            if d is None:
                continue
            env = dict(ALLOWED)
            env.update(d['features'])
            env['side'] = o['side']
            if not eval(code, {'__builtins__': {}}, env):
                continue
            n += 1
            rs.append(o['r'])
            if o['r'] > 0:
                wins += 1
        prev = bl.get('status', 'UNTESTED')
        cur = status_for(n, wins)
        out.append({**bl, 'n': n, 'wins': wins,
                    'win_rate': round(wins / n, 3) if n else None,
                    'mean_r': round(sum(rs) / n, 3) if n else None,
                    'status_prev': prev, 'status': cur,
                    'changed': prev != cur})
    return out


def load(path):
    return json.load(open(path)) if os.path.exists(path) else []


def save(path, beliefs):
    json.dump(beliefs, open(path, 'w'), ensure_ascii=False, indent=1)
