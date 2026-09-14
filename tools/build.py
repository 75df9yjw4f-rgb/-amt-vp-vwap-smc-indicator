#!/usr/bin/env python3
"""
ACE build tool - variant B (two builds from one source).

    build/ACE.pine      Standard : the L3 FOOTPRINT ADAPTER region is stripped.
                                   Contains no request.footprint() call, so it
                                   runs on every TradingView plan.
    build/ACE-Pro.pine  Pro      : the region is kept. Requires Premium/Ultimate.

The single source of truth is src/ACE.pine. The L3 region is delimited by the
markers below and is the ONLY place allowed to touch footprint APIs, so the
Standard build is produced by deletion alone - never by editing logic.

Usage:  python3 tools/build.py [--check]
        --check  verify the builds are in sync with the source (exit 1 if not)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "ACE.pine"
OUT_STD = ROOT / "build" / "ACE.pine"
OUT_PRO = ROOT / "build" / "ACE-Pro.pine"

BEGIN = "//  #region L3 FOOTPRINT ADAPTER"
END = "//  #endregion L3 FOOTPRINT ADAPTER"

# The Standard build still needs the two entry points the rest of the script
# calls, so the stripped region is replaced by inert stubs with identical
# signatures. Nothing else in the script changes between builds.
STUB = """//  L3 FOOTPRINT ADAPTER - REMOVED IN THE STANDARD BUILD
//
//  This build contains no request.footprint() call and therefore runs on every
//  TradingView plan. The Pro build (build/ACE-Pro.pine) keeps the adapter and
//  requires a Premium or Ultimate plan. Both are generated from src/ACE.pine.

//@function Always false in the Standard build: no footprint data is requested.
fpAvailable() =>
    false

//@function Inert in the Standard build.
fpBarContribution(Profile p) =>
    bool _unused = na(p)
    false
"""


def split_region(text: str):
    if BEGIN not in text or END not in text:
        sys.exit("error: L3 region markers not found in src/ACE.pine")
    head, rest = text.split(BEGIN, 1)
    _region, tail = rest.split(END, 1)
    return head, tail


def make_standard(text: str) -> str:
    head, tail = split_region(text)
    out = head + STUB + tail
    out = out.replace('const string ACE_BUILD   = "PRO"', 'const string ACE_BUILD   = "STD"')
    return out


def make_pro(text: str) -> str:
    return text


def verify(text: str, name: str) -> None:
    """Guard the invariant that makes variant B work at all."""
    code = "\n".join(
        line.split("//")[0] for line in text.splitlines() if line.split("//")[0].strip()
    )
    for token in ("barmerge.lookahead", "varip"):
        if token in code:
            sys.exit(f"error: {name} contains forbidden token {token!r}")
    if name == "ACE.pine" and "request.footprint" in code:
        sys.exit("error: Standard build still calls request.footprint()")


def main() -> int:
    check = "--check" in sys.argv
    src = SRC.read_text(encoding="utf-8")
    targets = [(OUT_STD, make_standard(src)), (OUT_PRO, make_pro(src))]

    stale = []
    for path, content in targets:
        verify(content, path.name)
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"{path.relative_to(ROOT)}  {len(content.splitlines())} lines")

    if check:
        if stale:
            print("out of date: " + ", ".join(stale))
            return 1
        print("builds are in sync with src/ACE.pine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
