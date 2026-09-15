"""CLI for the loop: `step N` runs until N trades close, then stops."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import run

BARS = 'research/loop/TEST.csv'
POL = 'research/loop/policies'
LED = 'research/loop/state/ledger.jsonl'

if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    made = run(BARS, POL, LED, stop_after_trades=n)
    print(f"--- закрыто сделок в этой партии: {made} ---")
