"""Renders decision inputs compactly, carrying only what the frozen prompt says
to weigh. Nothing is added, and nothing about the future can appear: the input
file has no outcome field to begin with.

Every field is printed through a None-safe formatter. A missing value is a real
state here - early bars have no confirmed swing, and the regime is unknown until
enough history exists - so it must render as 'na' rather than stop the run.
"""
import json, sys

def n(x, w=6, d=2, plus=True):
    if x is None:
        return "   na "
    return f"{x:{'+' if plus else ''}{w}.{d}f}"

def line(rec):
    s = rec["snapshot"]
    p, v, a = s["position_vs_value"], s["vwap"], s["ace_score"]
    st, t, d, rg = s["structure"], s["proposed_trade"], s["displacement"], s["regime"]
    sw_h, sw_l = st["bars_since_that_swing_high_confirmed"], st["bars_since_that_swing_low_confirmed"]
    return (
        f'{rec["probe_id"]:>10s} | {t["side"]:<5s} stop {n(t["stop_distance_atr"],5,2,False)}atr\n'
        f'           | VALUE  in_va={str(p["inside_developing_value_area"])[:5]:<5s} '
        f'poc{n(p["close_minus_dev_poc_atr"])} vah{n(p["close_minus_dev_vah_atr"])} '
        f'val{n(p["close_minus_dev_val_atr"])} w={n(p["dev_value_area_width_atr"],5,1,False)}\n'
        f'           | FLOW   vwap{n(v["close_minus_session_vwap_atr"])} '
        f'z{n(v["z_score_vs_primary_vwap"])} | {rg["label"]:<7s} '
        f'persist {rg["vwap_side_persistence_20"]}\n'
        f'           | SCORE  bias{n(a["bias"],6,3)} {a["context_strength"]:<8s} '
        f'd5{n(a["bias_change_last_5_bars"],6,3)}\n'
        f'           | STRUCT vs.swHi{n(st["close_minus_last_swing_high_atr"])}'
        f'({sw_h if sw_h is not None else "-"}b) '
        f'vs.swLo{n(st["close_minus_last_swing_low_atr"])}'
        f'({sw_l if sw_l is not None else "-"}b) '
        f'disp={d["last_direction"] if d["last_direction"] is not None else "-"}'
        f'/{d["bars_since"] if d["bars_since"] is not None else "-"}b')

recs = [json.loads(l) for l in open("research/out/decision_inputs.jsonl")]
lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, len(recs))
for r in recs[lo:hi]:
    print(line(r)); print()
