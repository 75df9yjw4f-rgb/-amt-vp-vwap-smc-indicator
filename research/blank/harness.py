"""Blank-chart harness. Input is time and OHLC only - no ACE column exists here.

Candidate definition, feature list and exits are frozen in docs/23. Features are
computed from bars <= i and nothing else; the exit simulation runs only after a
decision has been recorded, so it cannot reach back into it.
"""
import csv, json, statistics, sys

PUSH      = 0.75      # close position within the candidate bar
VOL_X     = 1.5       # bar range against the rolling median
LOOKBACK  = 20        # extreme window
MED_WIN   = 100
COOLDOWN  = 30
MAX_BARS  = 48
TP_PCT = SL_PCT = 0.15


def load(path):
    r = list(csv.DictReader(open(path)))
    return [{'t': int(x['time']), 'o': float(x['open']), 'h': float(x['high']),
             'l': float(x['low']), 'c': float(x['close'])} for x in r]


def med_range(b, i, w=MED_WIN):
    v = [b[j]['h'] - b[j]['l'] for j in range(max(0, i - w), i)]
    return statistics.median(v) if v else 0.0


def features(b, i):
    """Everything here reads bars <= i. The frozen list is docs/23 section 4."""
    import datetime
    cur = b[i]
    rng = cur['h'] - cur['l']
    med = med_range(b, i) or 1e-9
    hi20 = max(x['h'] for x in b[i - 20:i]); lo20 = min(x['l'] for x in b[i - 20:i])
    hi60 = max(x['h'] for x in b[max(0, i - 60):i])
    lo60 = min(x['l'] for x in b[max(0, i - 60):i])
    rets = [b[j]['c'] - b[j - 1]['c'] for j in range(max(1, i - 19), i + 1)]
    dt = datetime.datetime.utcfromtimestamp(cur['t'])
    # session open = first bar of this UTC day present in the data
    d0 = i
    while d0 > 0 and datetime.datetime.utcfromtimestamp(b[d0 - 1]['t']).date() == dt.date():
        d0 -= 1
    return {
        'hour_utc': dt.hour,
        'bar_pos': round((cur['c'] - cur['l']) / rng, 3) if rng > 0 else 0.5,
        'range_vs_med100': round(rng / med, 2),
        'net_move_20': round((cur['c'] - b[i - 20]['c']) / med, 2),
        'net_move_60': round((cur['c'] - b[max(0, i - 60)]['c']) / med, 2),
        'dist_from_hi20': round((cur['c'] - hi20) / med, 2),
        'dist_from_lo20': round((cur['c'] - lo20) / med, 2),
        'dist_from_hi60': round((cur['c'] - hi60) / med, 2),
        'dist_from_lo60': round((cur['c'] - lo60) / med, 2),
        'realized_vol_20': round(statistics.pstdev(rets) / med, 2) if len(rets) > 2 else 0,
        'range_60_vs_med': round((hi60 - lo60) / med, 2),
        'bars_since_session_open': i - d0,
        'close_vs_session_open': round((cur['c'] - b[d0]['o']) / med, 2),
    }


def candidates(b):
    out = []
    for i in range(MED_WIN + 1, len(b) - MAX_BARS - 1):
        rng = b[i]['h'] - b[i]['l']
        if rng <= 0:
            continue
        med = med_range(b, i)
        if med <= 0 or rng < VOL_X * med:
            continue
        pos = (b[i]['c'] - b[i]['l']) / rng
        hi = max(x['h'] for x in b[i - LOOKBACK:i])
        lo = min(x['l'] for x in b[i - LOOKBACK:i])
        if b[i]['h'] > hi and pos >= PUSH:
            out.append((i, 'push_up'))
        elif b[i]['l'] < lo and pos <= 1 - PUSH:
            out.append((i, 'push_dn'))
    return out


def simulate(b, i, side):
    e = b[i]['c']
    sgn = 1 if side == 'LONG' else -1
    stop = e - sgn * e * SL_PCT / 100.0
    target = e + sgn * e * TP_PCT / 100.0
    risk = abs(e - stop)
    mfe = mae = 0.0
    mfe_before_mae = None
    for k in range(1, MAX_BARS + 1):
        j = i + k
        if j >= len(b):
            return None
        x = b[j]
        fav = (x['h'] - e) if side == 'LONG' else (e - x['l'])
        adv = (e - x['l']) if side == 'LONG' else (x['h'] - e)
        mfe, mae = max(mfe, fav / risk), max(mae, adv / risk)
        if mfe_before_mae is None and mae >= 0.8:
            mfe_before_mae = mfe
        hs = (x['l'] <= stop) if side == 'LONG' else (x['h'] >= stop)
        ht = (x['h'] >= target) if side == 'LONG' else (x['l'] <= target)
        if hs:
            after = 0.0
            for m in range(k + 1, MAX_BARS + 1):
                if i + m >= len(b):
                    break
                y = b[i + m]
                f = (y['h'] - e) if side == 'LONG' else (e - y['l'])
                after = max(after, f / risk)
            return dict(r=-1.0, bars=k, outcome='STOP', mfe=mfe, mae=mae,
                        ambiguous=bool(ht), mfe_after_stop=after,
                        mfe_before_mae=mfe_before_mae)
        if ht:
            return dict(r=1.0, bars=k, outcome='TARGET', mfe=mfe, mae=mae,
                        ambiguous=False, mfe_after_stop=0.0,
                        mfe_before_mae=mfe_before_mae)
    x = b[min(i + MAX_BARS, len(b) - 1)]
    rm = ((x['c'] - e) if side == 'LONG' else (e - x['c'])) / risk
    return dict(r=rm, bars=MAX_BARS, outcome='TIME', mfe=mfe, mae=mae,
                ambiguous=False, mfe_after_stop=0.0, mfe_before_mae=mfe_before_mae)


if __name__ == '__main__':
    b = load(sys.argv[1] if len(sys.argv) > 1 else 'research/blank/FORWARD.csv')
    c = candidates(b)
    print(f"баров {len(b)}, кандидатов {len(c)}")
    # apply cooldown assuming a typical trade, to show the decision slots
    slots, busy = [], -999
    for i, d in c:
        if i < busy:
            continue
        slots.append((i, d))
        busy = i + 8 + COOLDOWN
    print(f"слотов решений при кулдауне {COOLDOWN}: {len(slots)}")
    json.dump([{'i': i, 'dir': d, 'f': features(b, i)} for i, d in slots],
              open('research/blank/slots.json', 'w'), indent=0)
    print("признаки записаны в research/blank/slots.json")
