"""Point-in-time snapshot construction.

The builder receives ONLY history[0..i]. Bars after the decision bar are not
passed in, so lookahead is prevented by the signature, not by discipline
(docs/15 section 7.1). lookahead_audit.py proves the harness honours that.

Everything is expressed in ATR units or ratios, and the instrument and dates are
dropped, to blunt the training-data contamination described in docs/14 section 9.3.
"""
import hashlib, json
from baselines import regime, ace_context

# Computed by ACE but never plotted, therefore absent from any export. Listed in
# every snapshot so the model can say what it lacks instead of guessing, and so
# the run measures which gaps actually bite (docs/14 section 1.4).
NOT_EXPORTABLE = [
    "component_contributions", "coverage_agreement_strength", "what_changed",
    "volume_profile_histogram", "static_poc_vah_val", "hvn_lvn",
    "structure_state", "hh_hl_lh_ll",
    "bos_level", "choch_level", "mss_level",
    "dealing_range", "premium_discount", "liquidity_levels", "eqh_eql",
    "liquidity_pools", "sweep_price", "fvg_boundaries", "fvg_mitigation",
    "amt_state", "balance_range",
    "acceptance_reference_and_magnitude", "initial_balance", "opening_range",
    "order_flow", "delta", "data_tier_l1_l2_l3",
]


def _d(a, b, atr):
    """Distance a-b in ATR units, or None if anything is missing."""
    if a is None or b is None or not atr:
        return None
    return round((a - b) / atr, 3)


def build(history, sig, symbol="ANON-1", timeframe="TF-A"):
    """history = rows[0..i]; sig = the baseline's proposed trade on bar i."""
    c = history[-1]
    atr = c.get('atr')
    reg, persistence, va_width = regime(history)

    # ACE plots the +/-2 and +/-3 sigma bands but not sigma, the primary VWAP or
    # the z-score. All three are recoverable from the two outer bands by
    # arithmetic: the midpoint is the VWAP the bands are built on, and a quarter
    # of their span is one sigma. This is derivation from exported values, not a
    # reconstruction of ACE's internals.
    center = sigma = z = None
    if c.get('band_u2') is not None and c.get('band_l2') is not None:
        center = (c['band_u2'] + c['band_l2']) / 2.0
        sigma = (c['band_u2'] - c['band_l2']) / 4.0
        if sigma and sigma > 0:
            z = round((c['close'] - center) / sigma, 3)

    def back(field, n):
        if len(history) <= n or history[-1 - n].get(field) is None \
           or c.get(field) is None:
            return None
        return round(c[field] - history[-1 - n][field], 3)

    inside_va = None
    if c.get('dev_vah') is not None and c.get('dev_val') is not None:
        inside_va = bool(c['dev_val'] <= c['close'] <= c['dev_vah'])

    snap = {
        "symbol": symbol,
        "timeframe": timeframe,
        "bar_seq": len(history) - 1,
        "position_vs_value": {
            "inside_developing_value_area": inside_va,
            "close_minus_dev_poc_atr": _d(c['close'], c.get('dev_poc'), atr),
            "close_minus_dev_vah_atr": _d(c['close'], c.get('dev_vah'), atr),
            "close_minus_dev_val_atr": _d(c['close'], c.get('dev_val'), atr),
            "dev_value_area_width_atr": va_width,
        },
        "vwap": {
            "close_minus_session_vwap_atr": _d(c['close'], c.get('vwap_sess'), atr),
            "close_minus_daily_vwap_atr":   _d(c['close'], c.get('vwap_day'), atr),
            "close_minus_weekly_vwap_atr":  _d(c['close'], c.get('vwap_week'), atr),
            "z_score_vs_primary_vwap": z,
            "note": "z derived from the exported +/-2 sigma bands",
        },
        "ace_score": {
            "bias": c.get('bias'), "confidence": c.get('confidence'),
            "bull": c.get('bull'), "bear": c.get('bear'),
            "context_strength": ace_context(c.get('bias')),
            "bias_change_last_5_bars": back('bias', 5),
            "confidence_change_last_5_bars": back('confidence', 5),
        },
        "regime": {"label": reg, "vwap_side_persistence_20": 
                   None if persistence is None else round(persistence, 3)},
        "proposed_trade": {
            "baseline": sig['baseline'], "side": sig['side'],
            "entry_is_current_close": True,
            "stop_distance_atr": round(abs(sig['entry'] - sig['stop']) / atr, 3) if atr else None,
            "target_distance_atr": round(abs(sig['target'] - sig['entry']) / atr, 3) if atr else None,
            "planned_rr": round(abs(sig['target'] - sig['entry']) /
                                abs(sig['entry'] - sig['stop']), 3)
                          if sig['entry'] != sig['stop'] else None,
        },
        "structure": {
            # Same convention as position_vs_value: close MINUS the level, so a
            # positive number always means price is above it. The two blocks
            # disagreed on this at first, which is precisely the kind of trap
            # that silently inverts a reading.
            "close_minus_last_swing_high_atr": _d(c['close'], c.get('sw_hi_px'), atr),
            "bars_since_that_swing_high_confirmed":
                None if c.get('sw_hi_bar') is None else len(history) - 1 - c['sw_hi_bar'],
            "close_minus_last_swing_low_atr": _d(c['close'], c.get('sw_lo_px'), atr),
            "bars_since_that_swing_low_confirmed":
                None if c.get('sw_lo_bar') is None else len(history) - 1 - c['sw_lo_bar'],
            "note": "positive = price above the level. Reconstructed from the "
                    "confirmation marker; known only from the confirmation bar "
                    "onward, never from the pivot bar",
        },
        "displacement": {
            "last_direction": c.get('disp_dir'),
            "bars_since": None if c.get('disp_bar') is None
                          else len(history) - 1 - c['disp_bar'],
        },
        "facts_unavailable": NOT_EXPORTABLE,
    }
    snap["snapshot_hash"] = hashlib.sha256(
        json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()
    return snap
