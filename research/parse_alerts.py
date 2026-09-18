"""Turns collected TradingView alert messages into the CSV the harness reads.

This is the fallback data path for accounts without chart-data export: a
heartbeat alert fires once per bar close and carries the plotted ACE values in
its message, and those messages are collected (email, alert log, webhook - the
sink does not matter here) and converted to the same schema load_csv() expects.

Input is deliberately forgiving. Alert exports come wrapped in mail headers,
quoted lines and forwarded junk, so every {...} object on any line is extracted
and anything that is not a snapshot is skipped rather than fought with.

It parses. It never invents: a field the alert did not carry stays empty, and
the harness reports it as absent.
"""
import csv, json, re, sys

FIELD_MAP = {                       # compact alert key -> harness CSV column
    "t": "time", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume",
    "poc": "Developing POC", "vah": "Developing VAH", "val": "Developing VAL",
    "vw": "Session VWAP", "vwd": "Daily VWAP", "vww": "Weekly VWAP",
    "u2": "VWAP +2σ", "l2": "VWAP -2σ", "u3": "VWAP +3σ", "l3": "VWAP -3σ",
    "bias": "BIAS", "conf": "CONFIDENCE", "bull": "BULL", "bear": "BEAR",
}
OBJ = re.compile(r'\{[^{}]*\}')


def parse(text):
    rows, skipped = [], 0
    for m in OBJ.finditer(text):
        raw = m.group(0)
        # TradingView writes na as an empty placeholder; make it valid JSON.
        cleaned = re.sub(r':\s*(,|\})', r': null\1', raw)
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if "t" not in obj or "c" not in obj:
            skipped += 1
            continue
        rows.append({FIELD_MAP[k]: v for k, v in obj.items() if k in FIELD_MAP})
    return rows, skipped


def dedupe(rows):
    """One row per bar. A repeated alert for the same bar is a duplicate, not a
    second bar; keeping both would double-count and quietly inflate the sample."""
    seen, out = set(), []
    for r in rows:
        t = r.get("time")
        if t in seen:
            continue
        seen.add(t)
        out.append(r)
    out.sort(key=lambda r: str(r.get("time")))
    return out


def main():
    if len(sys.argv) < 3:
        print("usage: parse_alerts.py <collected.txt> [more.txt ...] <out.csv>")
        return 2
    *sources, out_csv = sys.argv[1:]
    rows, skipped = [], 0
    for src in sources:
        r, s = parse(open(src, encoding="utf-8", errors="replace").read())
        rows += r
        skipped += s
        print(f"{src}: {len(r)} snapshots, {s} non-snapshot blocks ignored")

    before = len(rows)
    rows = dedupe(rows)
    cols = ["time", "open", "high", "low", "close", "volume"] + \
           [c for c in FIELD_MAP.values() if c not in
            ("time", "open", "high", "low", "close", "volume")]
    present = {c for r in rows for c in r}
    cols = [c for c in cols if c in present]

    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"{before} parsed -> {len(rows)} unique bars -> {out_csv}")
    print(f"columns carried: {len(cols)}")
    missing = sorted(set(FIELD_MAP.values()) - present)
    if missing:
        print("NOT carried by these alerts:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
