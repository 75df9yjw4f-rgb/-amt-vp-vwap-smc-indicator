"""Phase 1 held-out run and verdict. Verdict computed from docs/21 section 6."""
import os, random, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ace_data import load_csv
from baselines import regime
from phase1 import run

BOOT = 10000


def stats(rs):
    if not rs:
        return None
    w = [r for r in rs if r > 0]
    l = [r for r in rs if r <= 0]
    gw, gl = sum(w), -sum(l)
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dict(n=len(rs), exp=sum(rs) / len(rs), wr=len(w) / len(rs),
                pf=gw / gl if gl > 0 else float('inf'), total=eq, dd=dd)


def ci(rs, seed=7):
    rng = random.Random(seed)
    b = sorted(statistics.mean([rng.choice(rs) for _ in rs]) for _ in range(BOOT))
    return b[int(0.025 * BOOT)], b[int(0.975 * BOOT)]


def line(lab, s, extra=""):
    if not s:
        print(f"  {lab:<26s} нет сделок"); return
    print(f"  {lab:<26s} n={s['n']:4d}  exp {s['exp']:+.3f}R  wr {s['wr']:5.1%}"
          f"  PF {s['pf']:5.2f}  итог {s['total']:+8.2f}R  DD {s['dd']:6.2f}{extra}")


def main():
    rows, _, _ = load_csv('research/data/XAU-HELDOUT.csv')
    print("=" * 96)
    print("PHASE 1 — HELD-OUT (2026-08-21 → 09-08), TP=SL=0.15%, один прогон")
    print("=" * 96)

    results = {}
    for tag, thr in (('A', 0.15), ('B', 0.35)):
        t = run([dict(x) for x in rows], thr)
        results[tag] = t
        rs = [x['r'] for x in t]
        s = stats(rs)
        lo, hi = ci(rs) if rs else (0, 0)
        L = [x for x in t if x['side'] == 'LONG']
        S = [x for x in t if x['side'] == 'SHORT']
        amb = sum(1 for x in t if x['ambiguous'])
        tp = [x['bars'] for x in t if x['outcome'] == 'TARGET']
        sp = [x['bars'] for x in t if x['outcome'] == 'STOP']
        print(f"\n--- ВАРИАНТ {tag}: порог BIAS {thr} ---")
        line("итог", s)
        print(f"  CI95 ожидания: [{lo:+.4f}, {hi:+.4f}]")
        print(f"  LONG {len(L)} / SHORT {len(S)}   ambiguous баров: {amb}")
        print(f"  среднее время до TP: {statistics.mean(tp):.1f} бар "
              f"({len(tp)} шт)   до SL: {statistics.mean(sp):.1f} бар ({len(sp)} шт)")
        print(f"  исходы: " + ", ".join(
            f"{k}={sum(1 for x in t if x['outcome']==k)}"
            for k in ('TARGET', 'STOP', 'TIME')))
        results[tag + '_ci'] = (lo, hi)

    # ---------- exploratory breakdowns, all reported ----------
    t = results['A']
    print("\n" + "-" * 96)
    print("РАЗВЕДОЧНЫЕ РАЗРЕЗЫ (вариант A). Ни один не объявляется стратегией.")
    print("-" * 96)
    print("\nLONG против SHORT:")
    for side in ('LONG', 'SHORT'):
        line(side, stats([x['r'] for x in t if x['side'] == side]))

    print("\nразмер FVG (в ATR):")
    qs = sorted(x['fvg_size_atr'] for x in t)
    cuts = [qs[len(qs) // 3], qs[2 * len(qs) // 3]]
    for lab, f in ((f"малые < {cuts[0]:.2f}", lambda v: v < cuts[0]),
                   (f"средние {cuts[0]:.2f}-{cuts[1]:.2f}",
                    lambda v: cuts[0] <= v < cuts[1]),
                   (f"крупные >= {cuts[1]:.2f}", lambda v: v >= cuts[1])):
        line(lab, stats([x['r'] for x in t if f(x['fvg_size_atr'])]))

    print("\nвозраст FVG на входе:")
    for lab, f in (("<= 10 баров", lambda v: v <= 10),
                   ("11-30 баров", lambda v: 10 < v <= 30),
                   ("> 30 баров", lambda v: v > 30)):
        line(lab, stats([x['r'] for x in t if f(x['fvg_age'])]))

    print("\nрежим рынка на входе:")
    reg = {}
    for x in t:
        reg.setdefault(regime(rows[:x['bar'] + 1])[0], []).append(x['r'])
    for k in sorted(reg):
        line(k, stats(reg[k]))

    print("\nпервый ретест против повторных (отдельный прогон, allow_repeat):")
    tr = run([dict(x) for x in rows], 0.15, allow_repeat=True)
    line("только первые", stats([x['r'] for x in tr if x['first_retest']]))
    line("повторные", stats([x['r'] for x in tr if not x['first_retest']]))

    print("\nструктурный стоп за границей FVG (ОТДЕЛЬНЫЙ эксперимент):")
    ts = run([dict(x) for x in rows], 0.15, struct_stop=True)
    line("структурный стоп", stats([x['r'] for x in ts]),
         f"  ср. R:R {statistics.mean([x['rr'] for x in ts]):.2f}" if ts else "")

    # ---------- verdict, from the frozen table ----------
    rs = [x['r'] for x in results['A']]
    s = stats(rs)
    lo, hi = results['A_ci']
    print("\n" + "=" * 96)
    if s['exp'] >= 0.05 and lo > 0 and s['n'] >= 100:
        v, why = 'A', "сильное подтверждение: exp >= +0.05R, нижняя граница CI > 0, n >= 100"
    elif s['exp'] <= -0.05 and hi < 0:
        v, why = 'D', "отрицательный результат: exp <= -0.05R и верхняя граница CI < 0"
    elif s['exp'] > 0:
        v, why = 'B', "умеренное: ожидание положительно, но CI включает 0 либо n < 100"
    else:
        v, why = 'C', "преимущества не обнаружено"
    print(f"ВЕРДИКТ PHASE 1 (вариант A, основной): {v} — {why}")
    print("=" * 96)


if __name__ == '__main__':
    main()
