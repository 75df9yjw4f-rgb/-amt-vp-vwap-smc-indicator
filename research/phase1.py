"""Phase 1: trend continuation on a retest of a fresh FVG.

Purely mechanical. No model judgement anywhere in this file.

FVG and structure breaks are absent from the export, so both are rebuilt from
the literal definitions in src/ACE.pine - the gap conditions and minimum size
from lines 741-757, the close-through-level break from 887-899. The swing levels
they need come from the exported confirmation markers, verified against the data
at 1226 of 1226.

State is carried forward only: a bar depends on bars up to and including itself,
never on later ones. lookahead_phase1.py proves that rather than asserting it.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ace_data import SWING_LEN

MIN_FVG_ATR = 0.15      # ACE default minFvgAtr
FVG_MAX_AGE = 100       # pre-registered in docs/21 section 2.1, never tuned
MAX_BARS    = 48
TP_PCT = SL_PCT = 0.15  # same bracket as the Phase 0 primary


def run(rows, bias_thr, allow_repeat=False, swing_len=SWING_LEN,
        tp_pct=TP_PCT, sl_pct=SL_PCT, struct_stop=False,
        entries_only=False, _leak_next_bar=False):
    """One pass: build state, fire entries, resolve them. One position at a time.

    `entries_only` records entries without simulating exits or blocking on an
    open position. The audit needs it: with blocking on, an entry before bar i
    can legitimately change when a LATER bar moves, because the exit of an
    earlier trade decides whether a slot is free - which would make the audit
    fail for a reason that is not a leak.

    `_leak_next_bar` exists solely so the audit has something that must fail: it
    adds a condition on bar i+20, which no honest rule may touch. It looks that
    far ahead rather than one bar because a one-bar leak can only disturb an entry
    on bar i itself, and entries are sparse enough that the control would usually
    find nothing to disturb. An earlier
    attempt at a control - allowing the FVG to be read on its own formation bar -
    turned out to change nothing, because the zone is appended after the entry
    check in the same iteration, so it never reached the list in time. The audit
    caught that the control was inert, which is what a control is for.
    """
    sh = sl = None
    sh_broken = sl_broken = True
    struct_dir = 0
    zones = []
    trades = []
    busy_until = -1

    for i, r in enumerate(rows):
        # ---- confirmed swings become known on THIS bar, not on the pivot bar
        p = i - swing_len
        if r.get('swing_hi') is not None and p >= 0:
            sh, sh_broken = rows[p]['high'], False
        if r.get('swing_lo') is not None and p >= 0:
            sl, sl_broken = rows[p]['low'], False

        # ---- structure break, ACE closeBreak mode
        up = sh is not None and not sh_broken and r['close'] > sh
        dn = sl is not None and not sl_broken and r['close'] < sl
        take = (1 if r['close'] >= r['open'] else -1) if (up and dn) else \
               (1 if up else (-1 if dn else 0))
        if take == 1:
            sh_broken, struct_dir = True, 1
        elif take == -1:
            sl_broken, struct_dir = True, -1

        # ---- entry check uses only zones formed on EARLIER bars
        if (entries_only or i > busy_until) and r.get('gap_ok', True) \
           and r.get('bias') is not None and r.get('atr'):
            for z in zones:
                if z['bar'] >= i or i - z['bar'] > FVG_MAX_AGE:
                    continue
                if z['used'] and not allow_repeat:
                    continue
                hit = None
                if _leak_next_bar and i + 20 < len(rows):
                    nxt = rows[i + 20]
                    if (z['dir'] == 1 and nxt['close'] <= r['close']) or \
                       (z['dir'] == -1 and nxt['close'] >= r['close']):
                        continue
                if z['dir'] == 1 and struct_dir == 1 and r['bias'] >= bias_thr:
                    if r['low'] <= z['top'] and r['high'] >= z['bot'] \
                       and r['close'] > r['open'] and r['close'] > z['bot']:
                        hit = 'LONG'
                elif z['dir'] == -1 and struct_dir == -1 and r['bias'] <= -bias_thr:
                    if r['high'] >= z['bot'] and r['low'] <= z['top'] \
                       and r['close'] < r['open'] and r['close'] < z['top']:
                        hit = 'SHORT'
                if hit:
                    first = not z['used']
                    z['used'] = True
                    if entries_only:
                        trades.append({'bar': i, 'side': hit,
                                       'entry': round(r['close'], 5)})
                    else:
                        t = _enter(rows, i, hit, r, z, first, tp_pct,
                                   sl_pct, struct_stop)
                        if t:
                            trades.append(t)
                            busy_until = i + t['bars']
                    break

        # ---- FVG formed on this bar, confirmed at its close; tradable from i+1
        if i >= 2 and r.get('atr'):
            a = rows[i - 2]
            m = r['atr'] * MIN_FVG_ATR
            if r['low'] > a['high'] and (r['low'] - a['high']) >= m > 0:
                zones.append({'dir': 1, 'bot': a['high'], 'top': r['low'],
                              'bar': i, 'size': r['low'] - a['high'],
                              'atr': r['atr'], 'used': False})
            if r['high'] < a['low'] and (a['low'] - r['high']) >= m > 0:
                zones.append({'dir': -1, 'bot': r['high'], 'top': a['low'],
                              'bar': i, 'size': a['low'] - r['high'],
                              'atr': r['atr'], 'used': False})
        zones = [z for z in zones if i - z['bar'] <= FVG_MAX_AGE]
    return trades


def _enter(rows, i, side, r, z, first, tp_pct, sl_pct, struct_stop):
    e = r['close']
    sgn = 1 if side == 'LONG' else -1
    if struct_stop:
        stop = z['bot'] if side == 'LONG' else z['top']
        if (side == 'LONG' and stop >= e) or (side == 'SHORT' and stop <= e):
            return None
    else:
        stop = e - sgn * e * sl_pct / 100.0
    risk = abs(e - stop)
    if risk <= 0:
        return None
    target = e + sgn * e * tp_pct / 100.0
    rr = abs(target - e) / risk

    mfe = mae = 0.0
    for k in range(1, MAX_BARS + 1):
        j = i + k
        if j >= len(rows):
            return None                      # unresolved, excluded
        b = rows[j]
        fav = (b['high'] - e) if side == 'LONG' else (e - b['low'])
        adv = (e - b['low']) if side == 'LONG' else (b['high'] - e)
        mfe, mae = max(mfe, fav / risk), max(mae, adv / risk)
        hs = (b['low'] <= stop) if side == 'LONG' else (b['high'] >= stop)
        ht = (b['high'] >= target) if side == 'LONG' else (b['low'] <= target)
        if hs:                               # pessimistic: stop wins a tied bar
            return _t(i, side, e, z, first, -1.0, k, 'STOP', mfe, mae, ht, rr, r)
        if ht:
            return _t(i, side, e, z, first, rr, k, 'TARGET', mfe, mae, False, rr, r)
    b = rows[min(i + MAX_BARS, len(rows) - 1)]
    rm = ((b['close'] - e) if side == 'LONG' else (e - b['close'])) / risk
    return _t(i, side, e, z, first, rm, MAX_BARS, 'TIME', mfe, mae, False, rr, r)


def _t(i, side, e, z, first, rm, bars, out, mfe, mae, amb, rr, r):
    return {'bar': i, 'side': side, 'entry': e, 'r': rm, 'bars': bars,
            'outcome': out, 'mfe': mfe, 'mae': mae, 'ambiguous': bool(amb),
            'rr': rr, 'first_retest': first, 'fvg_age': i - z['bar'],
            'fvg_size_atr': z['size'] / z['atr'], 'bias': r['bias'],
            'time': r.get('time')}
