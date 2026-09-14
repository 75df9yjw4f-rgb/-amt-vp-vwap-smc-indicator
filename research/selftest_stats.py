"""Validates the statistics, not the market.

Builds decision logs whose veto skill is known by construction and checks that
the pre-registered verdict table (docs/15 section 5.4) returns the right branch
for each. The case that matters most is the skill-free one: a random veto MUST
NOT produce verdict A. If it did, every later result would be worthless.
"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import analyse


def veto_with(p_loser, p_winner):
    """Veto a loser with p_loser and a winner with p_winner.

    Written as one draw against a chosen probability on purpose: an earlier
    version used a chained ternary, where `r <= 0 and rng.random() < p` consumed
    a draw for losers only and then fell through to a second draw, so the real
    loser rate was p + (1-p)*p_winner rather than p. The bug was in the test, not
    in the metrics, but it would have silently mis-stated every calibration case.
    """
    return lambda r, rng: "VETO" if rng.random() < (p_loser if r <= 0 else p_winner) \
        else "ACCEPT"


def make_log(n, veto_fn, seed=1):
    """n trades with a realistic R distribution; veto_fn decides who is blocked."""
    rng = random.Random(seed)
    log = []
    for i in range(n):
        r = 2.0 if rng.random() < 0.40 else -1.0      # 40% win at 2R
        log.append({
            "bar_seq": i, "baseline": "B1", "regime": "TREND",
            "ace_context": "weak", "facts_missing": [], "hallucinated": False,
            "claude_decision": veto_fn(r, rng),
            "outcome": {"r_multiple": r, "mfe_r": 1.0, "mae_r": 0.5,
                        "outcome": "TARGET" if r > 0 else "STOP"},
        })
    return log


def case(name, veto_fn, expected, n=400, seed=1):
    """`expected` may be one verdict or several. Several is not laxity: where the
    true effect sits near the 0.20R bar, sampling decides between B and C and
    both are correct answers - the only wrong one is A."""
    allowed = {expected} if isinstance(expected, str) else set(expected)
    out = analyse(make_log(n, veto_fn, seed), seed=seed)
    got = out["verdict"]
    p = out.get("primary", {})
    ok = got in allowed
    print(f"  {'PASS' if ok else 'FAIL'}  {name:34s} expected {sorted(allowed)}, got {got}"
          f"   delta={p.get('delta_expectancy_r')} p={p.get('permutation_p')} "
          f"lift={out.get('veto_quality',{}).get('lift')}")
    return ok


def main():
    rng_rate = 0.35
    results = [
        # Skill-free: veto at random. The whole methodology rests on this one.
        case("random veto (no skill)", veto_with(0.35, 0.35), "C"),

        # Perfect knowledge, heavily degraded: vetoes losers 75% of the time.
        case("skilful veto (biased to losers)", veto_with(0.75, 0.05), "A"),

        # Inverted: vetoes the winners.
        case("inverted veto (vetoes winners)", veto_with(0.05, 0.75), "D"),

        # Barely-there skill: 36% of losers vetoed against 33% of winners. The
        # true separation is about 0.10R, below the 0.20R bar for verdict A, so
        # a correctly calibrated test must NOT call this substantial. This is
        # the check on the threshold's conservatism, not on its sensitivity.
        case("borderline skill (must not reach A)", veto_with(0.36, 0.33), ("B", "C")),
    ]
    print()
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
