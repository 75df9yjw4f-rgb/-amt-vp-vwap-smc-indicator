"""Renders decision inputs compactly, carrying only what the frozen prompt says
to weigh. Nothing is added and nothing about the future can appear here: the
input file has no outcome field to begin with."""
import json, sys

def line(rec):
    s = rec["snapshot"]
    p, v, a, st = (s["position_vs_value"], s["vwap"], s["ace_score"], s["structure"])
    t, d = s["proposed_trade"], s["displacement"]
    f = lambda x, n=2: "  na " if x is None else f"{x:+{n+4}.{n}f}"
    return (f'{rec["probe_id"]:>10s} | {t["side"]:<5s} rr {t["planned_rr"] or 0:.2f} '
            f'stop {t["stop_distance_atr"]:.2f}atr\n'
            f'           | VALUE  in_va={str(p["inside_developing_value_area"])[:5]:<5s} '
            f'poc{f(p["close_minus_dev_poc_atr"])} vah{f(p["close_minus_dev_vah_atr"])} '
            f'val{f(p["close_minus_dev_val_atr"])} w={p["dev_value_area_width_atr"]:.1f}\n'
            f'           | FLOW   vwap{f(v["close_minus_session_vwap_atr"])} '
            f'z{f(v["z_score_vs_primary_vwap"])} | {s["regime"]["label"]:<7s} '
            f'persist {s["regime"]["vwap_side_persistence_20"]}\n'
            f'           | SCORE  bias{f(a["bias"],3)} conf{f(a["confidence"],3)} '
            f'{a["context_strength"]:<8s} d5{f(a["bias_change_last_5_bars"],3)}\n'
            f'           | STRUCT vs.swingHi{f(st["close_minus_last_swing_high_atr"])}'
            f'({st["bars_since_that_swing_high_confirmed"]}b) '
            f'vs.swingLo{f(st["close_minus_last_swing_low_atr"])}'
            f'({st["bars_since_that_swing_low_confirmed"]}b) '
            f'disp={d["last_direction"]}/{d["bars_since"]}b')

recs = [json.loads(l) for l in open("research/out/decision_inputs.jsonl")]
lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, len(recs))
for r in recs[lo:hi]:
    print(line(r)); print()
