"""Imports a hand-collected Bar Replay table into the harness CSV schema.

Both automated routes out of TradingView are closed on a free account - chart
export and indicator alerts are alike paid - so the only remaining source of
genuine ACE values is reading the Data Window by hand. This accepts that reading
in whatever shape it arrives.

Input: one bar per line, values separated by tabs, commas, semicolons or runs of
spaces, with a header line naming the columns. Column order does not matter and
unknown columns are ignored. A blank, '-', 'n/a' or 'na' cell stays empty: a
value that was not readable is absent, not zero.
"""
import csv, re, sys

ALIASES = {
    'time': 'time', 't': 'time', 'bar': 'time', 'дата': 'time', 'время': 'time',
    'open': 'open', 'o': 'open', 'откр': 'open',
    'high': 'high', 'h': 'high', 'макс': 'high',
    'low': 'low', 'l': 'low', 'мин': 'low',
    'close': 'close', 'c': 'close', 'закр': 'close',
    'volume': 'volume', 'v': 'volume', 'vol': 'volume', 'объем': 'volume',
    'poc': 'Developing POC', 'developing poc': 'Developing POC',
    'vah': 'Developing VAH', 'developing vah': 'Developing VAH',
    'val': 'Developing VAL', 'developing val': 'Developing VAL',
    'vwap': 'Session VWAP', 'session vwap': 'Session VWAP', 'vw': 'Session VWAP',
    'u2': 'VWAP +2σ', 'vwap +2': 'VWAP +2σ', 'vwap +2σ': 'VWAP +2σ', '+2': 'VWAP +2σ',
    'l2': 'VWAP -2σ', 'vwap -2': 'VWAP -2σ', 'vwap -2σ': 'VWAP -2σ', '-2': 'VWAP -2σ',
    'u3': 'VWAP +3σ', 'l3': 'VWAP -3σ',
    'bias': 'BIAS', 'confidence': 'CONFIDENCE', 'conf': 'CONFIDENCE',
    'bull': 'BULL', 'bear': 'BEAR',
}
EMPTY = {'', '-', '--', 'n/a', 'na', 'nan', 'нет', '—'}


def split(line):
    if '\t' in line:
        return [c.strip() for c in line.split('\t')]
    if ';' in line:
        return [c.strip() for c in line.split(';')]
    if line.count(',') >= 2 and not re.search(r'\d,\d{3}\b', line):
        return [c.strip() for c in line.split(',')]
    return [c for c in re.split(r'\s{2,}|\s+', line.strip()) if c]


def clean_number(v):
    """Data Window copies carry thousands separators and non-breaking spaces."""
    v = v.replace(' ', '').replace(' ', '')
    if re.fullmatch(r'-?\d{1,3}(,\d{3})+(\.\d+)?', v):
        v = v.replace(',', '')
    elif re.fullmatch(r'-?\d+,\d+', v):        # decimal comma
        v = v.replace(',', '.')
    return v


def load(path):
    lines = [l.rstrip('\n') for l in open(path, encoding='utf-8-sig')
             if l.strip() and not l.lstrip().startswith('#')]
    if len(lines) < 2:
        raise ValueError("need a header line and at least one data line")

    header = [ALIASES.get(h.strip().lower()) for h in split(lines[0])]
    known = [h for h in header if h]
    if 'close' not in known:
        raise ValueError(f"no 'close' column recognised. Parsed header: {header}")

    rows, bad = [], 0
    for ln in lines[1:]:
        cells = split(ln)
        if len(cells) != len(header):
            bad += 1
            continue
        row = {}
        for name, cell in zip(header, cells):
            if not name:
                continue
            if cell.lower() in EMPTY:
                row[name] = ''
            elif name == 'time':
                row[name] = cell
            else:
                row[name] = clean_number(cell)
        rows.append(row)
    return rows, known, bad


def main():
    if len(sys.argv) != 3:
        print("usage: paste_import.py <pasted.txt> <out.csv>")
        return 2
    rows, known, bad = load(sys.argv[1])
    with open(sys.argv[2], 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=known)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} bars -> {sys.argv[2]}")
    print(f"columns recognised: {', '.join(known)}")
    if bad:
        print(f"{bad} line(s) skipped: cell count did not match the header")
    return 0


if __name__ == '__main__':
    sys.exit(main())
