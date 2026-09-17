"""The barrier test, with a negative control that must fail.

Self-contained on purpose: it builds its own bars and its own policy, so it
keeps working when the experiment state is empty. A safeguard that only runs
when an experiment happens to be loaded is a safeguard that goes quiet exactly
when a fresh experiment is starting.

A check that has never failed is not a check, so this proves twice: the real
decision path is invariant to the future, AND the same test catches a
deliberately leaky path.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from features import features   # noqa: E402
from policy import Policy       # noqa: E402

POLICY = Policy({
    'version': 0, 'effective_from_bar': 0,
    'hypothesis': {'id': 'TEST', 'statement': 'фиктивная, только для теста'},
    'exits': {'sl_pct': 0.3, 'tp_pct': 0.3, 'max_bars': 48, 'cooldown': 20},
    'rules': [{'id': 'T1', 'when': 'rng < 0.7', 'then': 'SHORT'},
              {'id': 'T2', 'when': 'pos > 0.8', 'then': 'LONG'}],
})


def synth_bars(n=900, seed=4):
    rng = random.Random(seed)
    px, out, t = 1000.0, [], 1700000000
    for k in range(n):
        px *= 1 + rng.gauss(0, 0.0012)
        hi = px * (1 + abs(rng.gauss(0, 0.0009)))
        lo = px * (1 - abs(rng.gauss(0, 0.0009)))
        out.append({'t': t + k * 900, 'o': px, 'c': px, 'h': hi, 'l': lo})
    return out


def mutate(b, frm, rng):
    out = [dict(x) for x in b]
    for k in range(frm, len(out)):
        s = out[k]['c'] * (1 + rng.uniform(-0.02, 0.02))
        out[k] = {'t': out[k]['t'], 'o': s, 'c': s, 'h': s * 1.003, 'l': s * 0.997}
    return out


def decide_clean(b, i):
    return POLICY.decide(features(b[:i + 1], i))[0]


def decide_leaky(b, i):
    """NEGATIVE CONTROL — reads bar i+20. Must be caught."""
    f = features(b[:i + 1], i)
    if i + 20 < len(b):
        f['rng'] = 0.1 if b[i + 20]['c'] < b[i]['c'] else 9.9
    return POLICY.decide(f)[0]


def run(fn, samples=60, seed=11):
    rng = random.Random(seed)
    b = synth_bars()
    leaks = 0
    for _ in range(samples):
        i = rng.randrange(200, len(b) - 100)
        if fn(mutate(b, i + 1, rng), i) != fn(b, i):
            leaks += 1
    return leaks, samples


def test_no_lookahead():
    leaks, n = run(decide_clean)
    assert leaks == 0, f'утечка: {leaks}/{n} решений изменились при мутации будущего'


def test_negative_control_is_caught():
    leaks, n = run(decide_leaky)
    assert leaks > 0, ('НЕГАТИВНЫЙ КОНТРОЛЬ НЕ СРАБОТАЛ — тест ничего не проверяет, '
                       f'заведомо протекающий код прошёл {n}/{n}')


if __name__ == '__main__':
    c, n = run(decide_clean)
    l, _ = run(decide_leaky)
    print(f"чистый путь:         утечек {c}/{n}   {'OK' if c == 0 else 'ПРОВАЛ'}")
    print(f"негативный контроль: утечек {l}/{n}   "
          f"{'OK (тест умеет падать)' if l > 0 else 'ПРОВАЛ — тест бесполезен'}")
    sys.exit(0 if (c == 0 and l > 0) else 1)
