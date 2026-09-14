"""Loading of a TradingView chart-data export, plus the one derived series the
harness is allowed to compute (ATR).

ACE is not modified, so the only ACE values that exist here are the ones the
script plots. Everything this module exposes comes either from the CSV or from
OHLC arithmetic; nothing is reconstructed or guessed.
"""
import csv, math, re

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

REQUIRED = ['open', 'high', 'low', 'close']
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

    rows.sort(key=lambda x: x.get('time') or '')
    add_atr(rows)
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
