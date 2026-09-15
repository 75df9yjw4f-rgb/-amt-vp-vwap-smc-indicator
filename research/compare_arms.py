"""Four-arm comparison for Phase 0. Run once, after all decisions exist.

Arms: the baseline alone, the baseline under Claude's veto, under a random veto
of the same size, and under the mechanical comparator M. The verdict comes from
the table in docs/15 section 5.4 and is computed, not written.
"""
import json, random, statistics, sys

BOOT, PERM = 10000, 10000


def stats(rs):
    if not rs:
        return {"n": 0}
    w = [r for r in rs if r > 0]
    l = [r for r in rs if r <= 0]
    gw, gl = sum(w), -sum(l)
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"n": len(rs), "exp": sum(rs) / len(rs), "wr": len(w) / len(rs),
            "pf": (gw / gl) if gl > 0 else float("inf"),
            "total": eq, "dd": dd,
            "avg_w": statistics.mean(w) if w else 0.0,
            "avg_l": statistics.mean(l) if l else 0.0}


def mech_M(snap, side):
    """The comparator: veto when bias opposes the side with size >= 0.15."""
    b = snap["ace_score"]["bias"]
    if b is None:
        return "ACCEPT"
    if side == "LONG" and b <= -0.15:
        return "VETO"
    if side == "SHORT" and b >= 0.15:
        return "VETO"
    return "ACCEPT"


def main():
    dec = {json.loads(l)["probe_id"]: json.loads(l)
           for l in open("research/out/decisions.jsonl")}
    inp = {json.loads(l)["probe_id"]: json.loads(l)["snapshot"]
           for l in open("research/out/decision_inputs.jsonl")}
    sig = [json.loads(l) for l in open("research/out/held_pct015.jsonl")]
    idx = json.load(open("research/out/sample_index.json"))
    rows = [sig[k] for k in idx["indices"]]

    recs = []
    for r in rows:
        pid = f"{r['baseline']}-{r['bar_seq']}"
        o = r.get("outcome", {})
        if o.get("r_multiple") is None or pid not in dec:
            continue
        recs.append({"pid": pid, "r": o["r_multiple"],
                     "claude": dec[pid]["decision"],
                     "M": mech_M(inp[pid], r["baseline_decision"]["side"]),
                     "base": r["baseline"], "regime": r["regime"],
                     "side": r["baseline_decision"]["side"],
                     "mfe": o.get("mfe_r"), "mae": o.get("mae_r"),
                     "bars": o.get("bars_held")})
    print(f"решений с разрешённым исходом: {len(recs)} из {len(rows)}")
    unresolved = len(rows) - len(recs)
    if unresolved:
        print(f"нерешённых (OPEN, отброшены): {unresolved}")

    allr = [x["r"] for x in recs]
    c_acc = [x["r"] for x in recs if x["claude"] == "ACCEPT"]
    c_vet = [x["r"] for x in recs if x["claude"] != "ACCEPT"]
    m_acc = [x["r"] for x in recs if x["M"] == "ACCEPT"]
    m_vet = [x["r"] for x in recs if x["M"] == "VETO"]

    rng = random.Random(20260914)
    k = len(c_vet)
    rand_exp, rand_wr, rand_pf, rand_dd = [], [], [], []
    for _ in range(2000):
        pool = allr[:]
        rng.shuffle(pool)
        s = stats(pool[k:])
        rand_exp.append(s["exp"]); rand_wr.append(s["wr"])
        rand_pf.append(s["pf"] if s["pf"] != float("inf") else 0)
        rand_dd.append(s["dd"])

    A, B, D = stats(allr), stats(c_acc), stats(m_acc)
    print("\n" + "=" * 78)
    print(f"{'АРМ':<34s}{'сделок':>7s}{'expect':>9s}{'winrate':>9s}"
          f"{'PF':>7s}{'итог R':>9s}{'maxDD':>8s}")
    print("=" * 78)
    def row(lab, s):
        print(f"{lab:<34s}{s['n']:>7d}{s['exp']:>+9.3f}{s['wr']:>8.1%}"
              f"{s['pf']:>7.2f}{s['total']:>+9.2f}{s['dd']:>8.2f}")
    row("1) Baseline (все сигналы)", A)
    row("2) Baseline + Claude VETO", B)
    print(f"{'3) Baseline + Random VETO (средн.)':<34s}{len(allr)-k:>7d}"
          f"{statistics.mean(rand_exp):>+9.3f}{statistics.mean(rand_wr):>8.1%}"
          f"{statistics.mean(rand_pf):>7.2f}"
          f"{statistics.mean(rand_exp)*(len(allr)-k):>+9.2f}"
          f"{statistics.mean(rand_dd):>8.2f}")
    row("4) Baseline + Mechanical M", D)

    print("\n--- отсечённые сделки: что именно было отсечено ---")
    for lab, v in (("Claude", c_vet), ("M", m_vet)):
        s = stats(v)
        if s["n"]:
            print(f"  {lab:<7s} отсёк {s['n']:3d} сделок, их ожидание "
                  f"{s['exp']:+.3f}R, winrate {s['wr']:.1%}")

    def delta_test(acc, vet, label):
        if not acc or not vet:
            print(f"  {label}: недостаточно данных"); return None
        d = statistics.mean(acc) - statistics.mean(vet)
        boot = []
        for _ in range(BOOT):
            a = [rng.choice(acc) for _ in acc]
            b = [rng.choice(vet) for _ in vet]
            boot.append(statistics.mean(a) - statistics.mean(b))
        boot.sort()
        lo, hi = boot[int(0.025 * BOOT)], boot[int(0.975 * BOOT)]
        pool, kk, ge = acc + vet, len(vet), 0
        for _ in range(PERM):
            rng.shuffle(pool)
            if statistics.mean(pool[kk:]) - statistics.mean(pool[:kk]) >= d:
                ge += 1
        p = (ge + 1) / (PERM + 1)
        print(f"  {label}: delta {d:+.4f}R   CI95 [{lo:+.3f}, {hi:+.3f}]   p={p:.4f}")
        return d, lo, hi, p

    print("\n--- главный тест: отделяет ли вето убыточные от прибыльных ---")
    print("    (нулевая гипотеза: случайное вето той же частоты)")
    cd = delta_test(c_acc, c_vet, "Claude")
    md = delta_test(m_acc, m_vet, "M     ")

    print("\n--- Claude против M напрямую ---")
    agree = sum(1 for x in recs if (x["claude"] == "ACCEPT") == (x["M"] == "ACCEPT"))
    print(f"  решения совпали: {agree}/{len(recs)} ({agree/len(recs):.1%})")
    only_c = [x["r"] for x in recs if x["claude"] != "ACCEPT" and x["M"] == "ACCEPT"]
    only_m = [x["r"] for x in recs if x["claude"] == "ACCEPT" and x["M"] == "VETO"]
    if only_c: print(f"  отсёк только Claude: {len(only_c)} сделок, "
                     f"ожидание {statistics.mean(only_c):+.3f}R")
    if only_m: print(f"  отсёк только M:      {len(only_m)} сделок, "
                     f"ожидание {statistics.mean(only_m):+.3f}R")
    print(f"  разница ожиданий арм: Claude {B['exp']:+.3f}R против M {D['exp']:+.3f}R "
          f"= {B['exp']-D['exp']:+.3f}R")

    print("\n--- матрица качества вето (Claude) ---")
    tp = sum(1 for r in c_vet if r <= 0); fp = sum(1 for r in c_vet if r > 0)
    base = sum(1 for r in allr if r <= 0) / len(allr)
    prec = tp / len(c_vet) if c_vet else 0
    print(f"  отсечено убыточных (верно):    {tp}")
    print(f"  отсечено прибыльных (ошибка):  {fp}")
    print(f"  точность вето {prec:.1%} против базовой доли убыточных {base:.1%}"
          f"  ->  lift {prec/base:.3f}")
    print("  lift <= 1.0 означает отсутствие умения, каким бы ни был P&L")

    print("\n--- разбивка по правилу ---")
    for b in sorted({x["base"] for x in recs}):
        sub = [x for x in recs if x["base"] == b]
        sa = stats([x["r"] for x in sub])
        sb = stats([x["r"] for x in sub if x["claude"] == "ACCEPT"])
        print(f"  {b}: всего {sa['n']:3d} exp {sa['exp']:+.3f}R  ->  "
              f"после вето {sb['n']:3d} exp {sb['exp'] if sb['n'] else 0:+.3f}R")

    # ---- вердикт по таблице docs/15 §5.4, считает программа ----
    print("\n" + "=" * 78)
    if cd is None:
        print("ВЕРДИКТ: INVALID"); return
    d, lo, hi, p = cd
    gates = []
    if len(recs) < 100: gates.append(f"сделок {len(recs)} < 100")
    if len(c_acc) < 30: gates.append(f"ACCEPT {len(c_acc)} < 30")
    if len(c_vet) < 30: gates.append(f"VETO {len(c_vet)} < 30")
    vr = len(c_vet) / len(recs)
    if not (0.10 <= vr <= 0.70): gates.append(f"доля вето {vr:.2f} вне 0.10-0.70")
    if gates:
        print("ВЕРДИКТ: INVALID —", "; ".join(gates)); return
    if d >= 0.20 and lo > 0 and p < 0.05:
        v, why = "A", "существенное улучшение: delta >= 0.20R, CI выше 0, p < 0.05"
    elif d < -0.05 and hi < 0:
        v, why = "D", "вето убирало лучшие сделки"
    elif d > 0.05:
        v, why = "B", "положительно, но не доказано: CI включает 0 или p >= 0.05"
    else:
        v, why = "C", "разделения между принятыми и отсечёнными нет"
    print(f"ВЕРДИКТ: {v} — {why}")
    print("=" * 78)


if __name__ == "__main__":
    main()
