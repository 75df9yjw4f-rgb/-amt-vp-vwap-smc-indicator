"""Append-only decision ledger.

Every decision is serialised and hashed BEFORE its outcome exists. The outcome
record carries the decision's hash. A postmortem that disagrees with the ledger
is a postmortem that was rewritten, and `verify` says so.

This is the mechanism that makes "the decision was fixed before the result was
known" checkable by a third party instead of promised by the author.
"""
import hashlib
import json
import os

CANON = dict(sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, **CANON).encode()).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)

    def append(self, kind, payload):
        rec = {'kind': kind, 'payload': payload, 'hash': digest(payload)}
        prev = self.tail_hash()
        rec['prev'] = prev
        rec['chain'] = digest({'p': prev, 'h': rec['hash']})
        with open(self.path, 'a') as fh:
            fh.write(json.dumps(rec, **CANON) + '\n')
        return rec

    def read(self):
        if not os.path.exists(self.path):
            return []
        return [json.loads(l) for l in open(self.path) if l.strip()]

    def tail_hash(self):
        recs = self.read()
        return recs[-1]['chain'] if recs else None

    def verify(self):
        """Returns (ok, problems). Checks payload hashes and the chain."""
        bad = []
        prev = None
        for n, r in enumerate(self.read()):
            if digest(r['payload']) != r['hash']:
                bad.append(f'запись {n}: payload не совпадает с hash')
            if r.get('prev') != prev:
                bad.append(f'запись {n}: разрыв цепочки')
            if digest({'p': r.get('prev'), 'h': r['hash']}) != r['chain']:
                bad.append(f'запись {n}: chain не совпадает')
            prev = r['chain']
        return (not bad), bad

    def decisions(self):
        return [r['payload'] for r in self.read() if r['kind'] == 'DECISION']

    def outcomes(self):
        return [r['payload'] for r in self.read() if r['kind'] == 'OUTCOME']
