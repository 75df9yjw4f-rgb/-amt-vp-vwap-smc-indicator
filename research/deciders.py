"""Veto deciders.

Three are provided. `accept_all` is arm A of the comparison. `random_veto` is the
null model the pre-registration tests against: a veto that removes the same
fraction of trades with no skill at all. `claude` is the real arm, and it is a
stub here because Phase 0 has no data yet - wiring it to the API before there is
anything to run it on would only spend money.
"""
import random


def accept_all(snapshot, rng=None):
    return {"decision": "ACCEPT", "reason_code": "NO_CONFLICT",
            "facts_used": [], "facts_missing": [], "conflicts": [],
            "self_confidence": "high", "reason": "baseline arm A: no veto layer"}


def make_random_veto(rate, seed=0):
    """Null model: veto `rate` of trades at random. Skill-free by construction."""
    rng = random.Random(seed)

    def decide(snapshot, _rng=None):
        veto = rng.random() < rate
        return {"decision": "VETO" if veto else "ACCEPT",
                "reason_code": "CONFLICT" if veto else "NO_CONFLICT",
                "facts_used": [], "facts_missing": [], "conflicts": [],
                "self_confidence": "low", "reason": "null model"}
    return decide


def claude_stub(snapshot, rng=None):
    raise NotImplementedError(
        "The Claude decider needs a real ACE export to run against. "
        "Put TradingView CSV files in research/data/ first; see docs/15 section 9.")
