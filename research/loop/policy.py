"""A policy is Claude's current behaviour, in executable form.

The point of making it executable rather than prose: a lesson that does not
change a rule changes nothing, and that becomes measurable instead of arguable.
Rules are ordered; the first whose condition holds decides. Nothing matches ->
HOLD.
"""
import json
import math

ALLOWED = {'abs': abs, 'min': min, 'max': max}
ACTIONS = ('LONG', 'SHORT', 'HOLD')


class Rule:
    def __init__(self, d):
        self.id = d['id']
        self.when = d['when']
        self.then = d['then']
        self.origin = d.get('origin', '')
        self.note = d.get('note', '')
        if self.then not in ACTIONS:
            raise ValueError(f'{self.id}: bad action {self.then}')
        self.code = compile(self.when, f'<rule {self.id}>', 'eval')

    def holds(self, f):
        env = dict(ALLOWED)
        env.update(f)
        return bool(eval(self.code, {'__builtins__': {}}, env))

    def to_dict(self):
        return {'id': self.id, 'when': self.when, 'then': self.then,
                'origin': self.origin, 'note': self.note}


class Policy:
    def __init__(self, d):
        self.version = d['version']
        self.effective_from_bar = d['effective_from_bar']
        self.hypothesis = d['hypothesis']
        self.exits = d['exits']
        self.rules = [Rule(r) for r in d['rules']]
        self.authored_after_trades = d.get('authored_after_trades')
        self.rationale = d.get('rationale', '')

    @classmethod
    def load(cls, path):
        return cls(json.load(open(path)))

    def decide(self, f):
        """Returns (action, rule_id). Pure function of the feature dict."""
        for r in self.rules:
            if r.holds(f):
                return r.then, r.id
        return 'HOLD', None

    def to_dict(self):
        return {'version': self.version,
                'effective_from_bar': self.effective_from_bar,
                'hypothesis': self.hypothesis, 'exits': self.exits,
                'rules': [r.to_dict() for r in self.rules],
                'authored_after_trades': self.authored_after_trades,
                'rationale': self.rationale}


def load_all(dirpath):
    import glob
    import os
    ps = [Policy.load(p) for p in sorted(glob.glob(os.path.join(dirpath, 'v*.json')))]
    ps.sort(key=lambda p: p.version)
    for a, b in zip(ps, ps[1:]):
        if b.effective_from_bar <= a.effective_from_bar:
            raise ValueError(f'v{b.version} must take effect after v{a.version}')
    return ps


def active_at(policies, bar):
    cur = None
    for p in policies:
        if p.effective_from_bar <= bar:
            cur = p
    if cur is None:
        raise ValueError(f'no policy active at bar {bar}')
    return cur
