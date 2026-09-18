"""Did the lesson change behaviour, or only the journal?

Two measurements, both mechanical:

  held_points  — at the decision points that actually occurred, what would the
                 OLD policy have said? This isolates the rule change from the
                 knock-on effect of trades opening at different bars.
  free_replay  — an independent walk of the whole segment under each policy.
                 Answers what the run would have looked like from the start.

A lesson with zero flips in `held_points` changed nothing. That is reported as
a failure of the lesson, not hidden.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import load, features     # noqa: E402
from engine import WARMUP, simulate     # noqa: E402


def at_points(decisions, old, new):
    """decisions: ledger DECISION payloads. Returns flip records."""
    flips = []
    for d in decisions:
        f = d['features']
        a_old, r_old = old.decide(f)
        a_new, r_new = new.decide(f)
        if a_old != a_new:
            flips.append({'bar': d['bar'], 'old': a_old, 'new': a_new,
                          'old_rule': r_old, 'new_rule': r_new,
                          'actual': d['action']})
    return flips


def free_replay(bars_path, policy, upto=None):
    b = load(bars_path)
    end = upto or len(b)
    busy = -1
    trades = []
    for i in range(WARMUP, end):
        if i < busy:
            continue
        f = features(b[:i + 1], i)
        a, rid = policy.decide(f)
        if a == 'HOLD':
            continue
        o = simulate(b, i, a, policy.exits)
        if o is None:
            break
        o.update({'bar': i, 'side': a, 'rule_id': rid})
        trades.append(o)
        busy = i + o['bars'] + policy.exits['cooldown']
    return trades
