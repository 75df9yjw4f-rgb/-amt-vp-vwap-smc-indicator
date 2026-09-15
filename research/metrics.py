"""Phase 0 metrics and the pre-registered verdict.

The verdict is computed from the table in docs/15 section 5.4. It is not written
by hand and not interpreted by eye.

The central test is NOT "arm B beats arm A". A veto only removes trades, so if
the baseline loses money then any veto improves it - including a coin flip. The
test that means something is whether the veto separates losers from winners
better than a random veto of the same rate, which is what the permutation test
below measures.
"""
import json, math, random, sys
from collections import Counter, defaultdict

MIN_SIGNALS, MIN_ACCEPT, MIN_VETO = 100, 30, 30
VETO_RATE_RANGE = (0.10, 0.70)
BOOT, PERM = 10000, 10000


def load(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _resolved(log):
    """Trades with a real outcome. OPEN trades ran off the end of the data and
    are excluded rather than closed at an invented price."""
    return [r for r in log
            if r.get("outcome", {}).get("r_multiple") is not None
            and not r.get("hallucinated")]


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _stats(rs):
    if not rs:
        return {"n": 0}
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_w, gross_l = sum(wins), -sum(losses)
    eq, peak, dd = 0.0, 0.0, 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {
        "n": len(rs),
        "expectancy_r": round(_mean(rs), 4),
        "win_rate": round(len(wins) / len(rs), 4),
        "avg_win_r": round(_mean(wins), 4) if wins else None,
        "avg_loss_r": round(_mean(losses), 4) if losses else None,
        "profit_factor": round(gross_w / gross_l, 4) if gross_l > 0 else None,
        "total_r": round(eq, 4),
        "max_drawdown_r": round(dd, 4),
    }


def analyse(log, seed=0):
    rng = random.Random(seed)
    res = _resolved(log)
    dec = Counter(r["claude_decision"] for r in log)
    n_sig = len(log)
    blocked = dec["VETO"] + dec["HOLD"]

    acc = [r["outcome"]["r_multiple"] for r in res if r["claude_decision"] == "ACCEPT"]
    vet = [r["outcome"]["r_multiple"] for r in res if r["claude_decision"] in ("VETO", "HOLD")]

    out = {
        "counts": {
            "signals": n_sig, "accept": dec["ACCEPT"], "veto": dec["VETO"],
            "hold": dec["HOLD"],
            "veto_rate": round(blocked / n_sig, 4) if n_sig else None,
            "resolved": len(res),
            "unresolved_open": sum(1 for r in log
                                   if r.get("outcome", {}).get("outcome") == "OPEN"),
            "hallucinated": sum(1 for r in log if r.get("hallucinated")),
        },
        "arm_A_all_signals": _stats([r["outcome"]["r_multiple"] for r in res]),
        "arm_B_accepted_only": _stats(acc),
        "vetoed_trades": _stats(vet),
    }

    # ---- validity gates, checked before anything is interpreted -------------
    gates = []
    if n_sig < MIN_SIGNALS:
        gates.append(f"signals {n_sig} < {MIN_SIGNALS}")
    if len(acc) < MIN_ACCEPT:
        gates.append(f"accepted {len(acc)} < {MIN_ACCEPT}")
    if len(vet) < MIN_VETO:
        gates.append(f"vetoed {len(vet)} < {MIN_VETO}")
    vr = out["counts"]["veto_rate"]
    if vr is not None and not (VETO_RATE_RANGE[0] <= vr <= VETO_RATE_RANGE[1]):
        gates.append(f"veto rate {vr} outside {VETO_RATE_RANGE}")
    out["validity_gate_failures"] = gates

    if gates:
        out["verdict"] = "INVALID"
        out["verdict_reason"] = ("Pre-registered minimum sample not met. This is "
                                 "not a negative result - the run does not "
                                 "measure anything.")
        return out

    # ---- primary statistic --------------------------------------------------
    delta = _mean(acc) - _mean(vet)

    boot = []
    for _ in range(BOOT):
        a = [rng.choice(acc) for _ in acc]
        v = [rng.choice(vet) for _ in vet]
        boot.append(_mean(a) - _mean(v))
    boot.sort()
    ci_lo, ci_hi = boot[int(0.025 * BOOT)], boot[int(0.975 * BOOT)]

    # Null model: same number of vetoes, assigned at random.
    pool = acc + vet
    k = len(vet)
    ge = 0
    for _ in range(PERM):
        rng.shuffle(pool)
        d = _mean(pool[k:]) - _mean(pool[:k])
        if d >= delta:
            ge += 1
    p = (ge + 1) / (PERM + 1)

    out["primary"] = {
        "delta_expectancy_r": round(delta, 4),
        "ci95": [round(ci_lo, 4), round(ci_hi, 4)],
        "permutation_p": round(p, 5),
        "null_model": "random veto of the same rate",
    }

    # ---- veto quality matrix (docs/15 section 5.6) --------------------------
    tp = sum(1 for r in vet if r <= 0)      # correctly stopped a loser
    fp = sum(1 for r in vet if r > 0)       # stopped a winner
    base_loss_rate = sum(1 for r in acc + vet if r <= 0) / len(acc + vet)
    prec = tp / len(vet) if vet else None
    total_losers = sum(1 for r in acc + vet if r <= 0)
    out["veto_quality"] = {
        "vetoed_that_would_have_lost": tp,
        "vetoed_that_would_have_won": fp,
        "veto_precision": round(prec, 4) if prec is not None else None,
        "veto_recall": round(tp / total_losers, 4) if total_losers else None,
        "base_loss_rate": round(base_loss_rate, 4),
        "lift": round(prec / base_loss_rate, 4) if prec and base_loss_rate else None,
        "lift_note": "lift <= 1.0 means no skill, whatever the P&L says",
    }

    # ---- breakdowns ---------------------------------------------------------
    for key, label in (("regime", "by_regime"), ("ace_context", "by_ace_context"),
                       ("baseline", "by_baseline")):
        g = defaultdict(lambda: {"accept": [], "veto": []})
        for r in res:
            arm = "accept" if r["claude_decision"] == "ACCEPT" else "veto"
            g[r.get(key)][arm].append(r["outcome"]["r_multiple"])
        out[label] = {k: {"accepted": _stats(v["accept"]),
                          "vetoed": _stats(v["veto"])} for k, v in g.items()}

    mfes = [r["outcome"]["mfe_r"] for r in res if r["outcome"].get("mfe_r") is not None]
    maes = [r["outcome"]["mae_r"] for r in res if r["outcome"].get("mae_r") is not None]
    out["excursions"] = {"avg_mfe_r": round(_mean(mfes), 4),
                         "avg_mae_r": round(_mean(maes), 4)}

    fm = Counter(f for r in log for f in r.get("facts_missing", []))
    out["most_requested_missing_facts"] = fm.most_common(15)

    # ---- verdict, straight from the pre-registered table --------------------
    if delta >= 0.20 and ci_lo > 0 and p < 0.05:
        v, why = "A", "substantial improvement: delta >= 0.20R, CI above 0, p < 0.05"
    elif delta < -0.05 and ci_hi < 0:
        v, why = "D", "the veto removed the better trades"
    elif delta > 0.05:
        v, why = "B", "positive but not established: CI includes 0 or p >= 0.05"
    else:
        v, why = "C", "no separation between accepted and vetoed trades"
    out["verdict"], out["verdict_reason"] = v, why
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "research/out/decisions.jsonl"
    print(json.dumps(analyse(load(path)), indent=2, ensure_ascii=False))
