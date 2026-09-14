"""Loading of a TradingView chart-data export, plus the one derived series the
harness is allowed to compute (ATR).

ACE is not modified, so the only ACE values that exist here are the ones the
script plots. Everything this module exposes comes either from the CSV or from
OHLC arithmetic; nothing is reconstructed or guessed.
"""
import csv, math, re
from datetime import datetime

# Canonical field name -> the spellings a TradingView export may use. Titles come
# straight from plot() calls in ACE, and the sigma character survives the export,
# so both spellings are accepted rather than assumed.
COLUMNS = {
    'time':      ['time', 'date', 'datetime'],
    'open':      ['open'],
    'high':      ['high'],
    'low':       ['low'],
    'close':     ['close'],
    'volume':    ['volume', 'vol'],
    'dev_poc':   ['developing poc'],
    'dev_vah':   ['developing vah'],
    'dev_val':   ['developing val'],
    'vwap_sess': ['session vwap'],
    'vwap_day':  ['daily vwap'],
    'vwap_week': ['weekly vwap'],
    'vwap_mon':  ['monthly vwap'],
    'avwap1':    ['anchored vwap 1'],
    'avwap2':    ['anchored vwap 2'],
    'band_u2':   ['vwap +2σ', 'vwap +2s', 'vwap +2 sigma', 'vwap plus 2 sigma'],
    'band_l2':   ['vwap -2σ', 'vwap -2s', 'vwap -2 sigma', 'vwap minus 2 sigma'],
    'band_u3':   ['vwap +3σ', 'vwap +3s', 'vwap +3 sigma', 'vwap plus 3 sigma'],
    'band_l3':   ['vwap -3σ', 'vwap -3s', 'vwap -3 sigma', 'vwap minus 3 sigma'],
    'bias':      ['bias'],
    'confidence':['confidence'],
    'bull':      ['bull'],
    'bear':      ['bear'],
}

# `open` and `volume` are never read: ATR uses high/low/previous close, the
# baselines and the snapshot use close, and outcomes use high/low/close. They
# stay optional so a hand-collected table does not have to carry them.
REQUIRED = ['high', 'low', 'close']
ATR_LEN = 14          # matches atrLen in ACE; see docs/15 section 2.2


def _norm(s):
    return re.sub(r'\s+', ' ', s.strip().lower())


def _num(v):
    if v is None:
        return None
    v = v.strip()
    if v == '' or v.upper() in ('NAN', 'NA', 'NULL'):
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    return None if math.isnan(f) else f


def load_csv(path):
    """Returns (rows, present, missing).

    `present` and `missing` name which ACE fields the export actually carried.
    `missing` is not an error: with ACE unmodified most of the context simply is
    not exportable, and the harness reports that rather than inventing it.
    """
    with open(path, newline='', encoding='utf-8-sig') as fh:
        rd = csv.DictReader(fh)
        raw = list(rd)
        headers = {_norm(h): h for h in (rd.fieldnames or [])}

    mapping = {}
    for field, spellings in COLUMNS.items():
        for sp in spellings:
            if sp in headers:
                mapping[field] = headers[sp]
                break

    for req in REQUIRED:
        if req not in mapping:
            raise ValueError(f"required column '{req}' not found in {path}")

    rows = []
    for r in raw:
        row = {f: _num(r.get(col)) for f, col in mapping.items() if f != 'time'}
        if 'time' in mapping:
            row['time'] = (r.get(mapping['time']) or '').strip()
        if row.get('close') is None:
            continue
        rows.append(row)

    rows.sort(key=_sort_key)
    add_atr(rows)
    mark_gaps(rows)
    present = sorted(mapping)
    missing = sorted(set(COLUMNS) - set(mapping))
    return rows, present, missing


def add_atr(rows, length=ATR_LEN):
    """Wilder's ATR, written into each row as `atr`.

    Seeded with a simple mean of the first `length` true ranges, which is what
    ta.atr does; before that point atr stays None and the harness skips the bar
    rather than trading on a half-formed average.
    """
    trs = []
    for i, r in enumerate(rows):
        if i == 0:
            tr = r['high'] - r['low']
        else:
            pc = rows[i - 1]['close']
            tr = max(r['high'] - r['low'], abs(r['high'] - pc), abs(r['low'] - pc))
        trs.append(tr)
        r['tr'] = tr

    atr = None
    for i, r in enumerate(rows):
        if i + 1 < length:
            r['atr'] = None
        elif i + 1 == length:
            atr = sum(trs[:length]) / length
            r['atr'] = atr
        else:
            atr = (atr * (length - 1) + trs[i]) / length
            r['atr'] = atr
    return rows


def _ts(v):
    """Seconds since epoch from a unix number or an ISO-8601 string, else None.

    Exports and alert messages do not agree on a time format, so both are
    accepted rather than one being assumed.
    """
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        pass
    txt = str(v).strip().replace('Z', '+00:00')
    for fmt in (None, '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            dt = datetime.fromisoformat(txt) if fmt is None \
                else datetime.strptime(txt, fmt)
            return dt.timestamp()
        except (ValueError, OSError):
            continue
    return None


def _sort_key(row):
    t = _ts(row.get('time'))
    return (0, t) if t is not None else (1, str(row.get('time') or ''))


def mark_gaps(rows):
    """Flags bars whose predecessor is more than one timeframe away.

    Forward collection through alerts drops bars: delivery is not guaranteed and
    sessions break. A hole is an absent bar, not a bar of zero movement, so a
    baseline comparing two rows across a hole would read a cross that never
    happened. Such signals are discarded (docs/15, Amendment 1).

    The interval is taken as the median spacing rather than a configured value,
    so the rule works on any timeframe without being told which.
    """
    ts = [_ts(r.get('time')) for r in rows]
    deltas = sorted(b - a for a, b in zip(ts, ts[1:])
                    if a is not None and b is not None and b > a)
    if not deltas:
        for r in rows:
            r['gap_ok'] = True          # no usable timestamps: rule cannot apply
        return rows
    interval = deltas[len(deltas) // 2]
    tol = interval * 1.5
    for i, r in enumerate(rows):
        if i == 0 or ts[i] is None or ts[i - 1] is None:
            r['gap_ok'] = i > 0
        else:
            r['gap_ok'] = (ts[i] - ts[i - 1]) <= tol
    return rows
