"""The kill path must be able to fire, or "the hypothesis survived" means nothing.

On the real run no kill criterion triggered. That is only informative if the
mechanism would have triggered on a genuinely failing record — so this feeds it
one and requires REJECTED.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import beliefs as B   # noqa: E402


def synth(n, wins, net20=-1.0):
    decs, outs = {}, []
    for k in range(n):
        h = f'h{k}'
        decs[h] = {'features': {'net20': net20, 'rng': 0.3, 'span20': 3.0}}
        outs.append({'decision_hash': h, 'side': 'SHORT',
                     'r': 1.0 if k < wins else -1.0})
    return outs, decs


BEL = [{'id': 'X', 'statement': 't', 'scope': 'net20 > -2.0', 'status': 'HELD'}]


def test_rejected_fires():
    outs, decs = synth(20, 4)          # 20% побед — заведомо провальная запись
    e = B.evaluate(BEL, outs, decs)[0]
    assert e['status'] == 'REJECTED', e
    assert e['changed'] is True


def test_weakened_fires():
    outs, decs = synth(20, 8)          # 40%
    assert B.evaluate(BEL, outs, decs)[0]['status'] == 'WEAKENED'


def test_small_sample_stays_untested():
    outs, decs = synth(5, 0)           # 0% побед, но n<8
    assert B.evaluate(BEL, outs, decs)[0]['status'] == 'UNTESTED'


def test_held_survives():
    outs, decs = synth(20, 11)
    assert B.evaluate(BEL, outs, decs)[0]['status'] == 'HELD'


if __name__ == '__main__':
    for f in (test_rejected_fires, test_weakened_fires,
              test_small_sample_stays_untested, test_held_survives):
        f()
        print(f'  {f.__name__}: OK')
    print('механизм убийства работает — значит "гипотеза выжила" это факт, а не молчание кода')
