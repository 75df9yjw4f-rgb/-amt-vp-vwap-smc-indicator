"""Emits decisions for the pending batch under the policy frozen in docs/23.

Policy (fixed before the run, unchanged since):
  default  fade the push        push_up -> SHORT, push_dn -> LONG
  HOLD     when fading would fight a strong 60-bar run, i.e.
           run60 = |net_move_60| / range_60_vs_med > 0.6

This file exists so the rule is applied identically on every batch and cannot
drift with the journal. It adds no new inputs.
"""
import json, os, sys

RUN60_MAX = 0.6

st = json.load(open('research/blank/state.json'))
out = []
for s in st['pending']:
    f = s['f']
    run = abs(f['net_move_60']) / f['range_60_vs_med'] if f['range_60_vs_med'] else 0.0
    if run > RUN60_MAX:
        out.append({'idx': s['idx'], 'decision': 'HOLD',
                    'reason': f'run60 {run:.2f} > 0.6 — fade fights a strong 60-bar run'})
    else:
        d = 'SHORT' if s['dir'] == 'push_up' else 'LONG'
        out.append({'idx': s['idx'], 'decision': d,
                    'reason': f'fade {s["dir"]}, run60 {run:.2f} <= 0.6'})
json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
for o in out:
    print(o['idx'], o['decision'], o['reason'])
