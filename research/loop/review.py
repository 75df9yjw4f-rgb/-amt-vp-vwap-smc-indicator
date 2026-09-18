"""Append Claude's between-batch reasoning to the same ledger as the decisions.

Postmortem, lesson, belief change and the resulting policy action live in the
audit trail, not in a side document — so a lesson can be traced to the decisions
it did or did not change.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import Ledger   # noqa: E402

LED = 'research/loop/state/ledger.jsonl'

if __name__ == '__main__':
    payload = json.load(open(sys.argv[1]))
    rec = Ledger(LED).append('REVIEW', payload)
    print(f"REVIEW #{payload['batch']} записан, hash {rec['hash'][:12]}")
