"""The barrier test, with a negative control that must fail.

A check that has never failed is not a check. So this file proves twice over:
the real decision path is invariant to the future, AND the same test catches a
deliberately leaky path. If the negative control ever passes, the test itself is
broken and the positive result means nothing.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from features import load, features     # noqa: E402
from policy import load_all, active_at  # noqa: E402

BARS = os.path.join(os.path.dirname(HERE), 'TEST.csv')
POLS = os.path.join(os.path.dirname(HERE), 'policies')


def mutate(b, frm, rng):
    """Replace every bar from `frm` onward with noise."""
    out = [dict(x) for x in b]
    for k in range(frm, len(out)):
        s = out[k]['c'] * (1 + rng.uniform(-0.02, 0.02))
        out[k] = {'t': out[k]['t'], 'o': s, 'c': s,
                  'h': s * 1.003, 'l': s * 0.997}
    return out


def decide_clean(b, i, pol):
    return pol.decide(features(b[:i + 1], i))[0]


def decide_leaky(b, i, pol):
    """NEGATIVE CONTROL — reads bar i+20. Must be caught."""
    f = features(b[:i + 1], i)
    if i + 20 < len(b):
        f['rng'] = 0.1 if b[i + 20]['c'] < b[i]['c'] else 9.9
    return pol.decide(f)[0]


def run(fn, samples=60, seed=11):
    rng = random.Random(seed)
    b = load(BARS)
    pol = load_all(POLS)[0]
    leaks = 0
    for _ in range(samples):
        i = rng.randrange(200, len(b) - 100)
        a = fn(b, i, pol)
        bm = mutate(b, i + 1, rng)
        if fn(bm, i, pol) != a:
            leaks += 1
    return leaks, samples


def test_no_lookahead():
    leaks, n = run(decide_clean)
    assert leaks == 0, f'утечка: {leaks}/{n} решений изменились при мутации будущего'


def test_negative_control_is_caught():
    leaks, n = run(decide_leaky)
    assert leaks > 0, ('НЕГАТИВНЫЙ КОНТРОЛЬ НЕ СРАБОТАЛ — тест ничего не проверяет, '
                       f'заведомо протекающий код прошёл {n}/{n}')
    return leaks, n


if __name__ == '__main__':
    c, n = run(decide_clean)
    l, _ = run(decide_leaky)
    print(f"чистый путь:        утечек {c}/{n}   {'OK' if c == 0 else 'ПРОВАЛ'}")
    print(f"негативный контроль: утечек {l}/{n}   "
          f"{'OK (тест умеет падать)' if l > 0 else 'ПРОВАЛ — тест бесполезен'}")
    sys.exit(0 if (c == 0 and l > 0) else 1)
