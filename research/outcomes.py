"""Forward simulation of a baseline signal.

This is the only place in the harness that looks at bars after the decision, and
it runs strictly after the decision has been recorded. The decision functions
never receive this module's output - that separation is what keeps the outcome
out of the snapshot.
"""
from baselines import MAX_BARS, BIAS_NEUTRAL


def simulate(rows, i, sig, max_bars=MAX_BARS):
    """Walk forward from the bar AFTER the signal bar and resolve the trade.

    Pessimistic convention, fixed in docs/15: when a single bar contains both the
    stop and the target, the stop is taken. Intrabar order is unknowable from
    OHLC, and assuming the good fill would flatter every result here.
    """
    entry, stop, target = sig['entry'], sig['stop'], sig['target']
    long_ = sig['side'] == 'LONG'
    risk = abs(entry - stop)
    if risk <= 0:
        return None

    mfe = mae = 0.0
    for k in range(1, max_bars + 1):
        j = i + k
        if j >= len(rows):
            # Ran off the end of the data: unresolved, and excluded from stats
            # rather than closed at an arbitrary price.
            return {'outcome': 'OPEN', 'exit_price': None, 'bars_held': k - 1,
                    'r_multiple': None, 'mfe_r': mfe, 'mae_r': mae}
        r = rows[j]
        fav = (r['high'] - entry) if long_ else (entry - r['low'])
        adv = (entry - r['low']) if long_ else (r['high'] - entry)
        mfe = max(mfe, fav / risk)
        mae = max(mae, adv / risk)

        hit_stop = (r['low'] <= stop) if long_ else (r['high'] >= stop)
        hit_tgt = (r['high'] >= target) if long_ else (r['low'] <= target)
        if hit_stop:
            return {'outcome': 'STOP', 'exit_price': stop, 'bars_held': k,
                    'r_multiple': -1.0, 'mfe_r': mfe, 'mae_r': mae}
        if hit_tgt:
            rr = (target - entry) / risk if long_ else (entry - target) / risk
            return {'outcome': 'TARGET', 'exit_price': target, 'bars_held': k,
                    'r_multiple': rr, 'mfe_r': mfe, 'mae_r': mae}

        if sig.get('exit_on_bias_neutral') and r.get('bias') is not None \
           and abs(r['bias']) < BIAS_NEUTRAL:
            rr = (r['close'] - entry) / risk if long_ else (entry - r['close']) / risk
            return {'outcome': 'NEUTRAL_EXIT', 'exit_price': r['close'], 'bars_held': k,
                    'r_multiple': rr, 'mfe_r': mfe, 'mae_r': mae}

    r = rows[min(i + max_bars, len(rows) - 1)]
    rr = (r['close'] - entry) / risk if long_ else (entry - r['close']) / risk
    return {'outcome': 'TIME', 'exit_price': r['close'], 'bars_held': max_bars,
            'r_multiple': rr, 'mfe_r': mfe, 'mae_r': mae}
