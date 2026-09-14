"""The three mechanical baselines and the regime classifier.

Every rule and every constant here is fixed by docs/15 (the pre-registration)
and must not be changed after a run. They are deliberately primitive: the point
of Phase 0 is not to find a good strategy, it is to have a stable reference that
the veto layer can be measured against.

Each baseline sees history[0..i] only. Future bars are not passed in, so
lookahead is prevented by the signature rather than by convention.
"""

STOP_ATR   = 1.5
TARGET_ATR = 3.0      # B1 only; B2/B3 take their target from an ACE level
MAX_BARS   = 48
BIAS_NEUTRAL = 0.15   # thrNeutral, ACE's own default - not a tuned value


def _ok(*vals):
    return all(v is not None for v in vals)


def b1_bias_flip(h):
    """B1 - momentum. BIAS leaving the neutral zone."""
    if len(h) < 2:
        return None
    c, p = h[-1], h[-2]
    if not _ok(c.get('bias'), p.get('bias'), c.get('atr')) or c['atr'] <= 0:
        return None
    if p['bias'] <= BIAS_NEUTRAL < c['bias']:
        side = 'LONG'
    elif p['bias'] >= -BIAS_NEUTRAL > c['bias']:
        side = 'SHORT'
    else:
        return None
    e, a = c['close'], c['atr']
    sgn = 1 if side == 'LONG' else -1
    return {'baseline': 'B1', 'side': side, 'entry': e,
            'stop': e - sgn * STOP_ATR * a, 'target': e + sgn * TARGET_ATR * a,
            'exit_on_bias_neutral': True}


def b2_va_return(h):
    """B2 - mean reversion. Close leaves the developing value area and comes back."""
    if len(h) < 2:
        return None
    c, p = h[-1], h[-2]
    if not _ok(c.get('dev_vah'), c.get('dev_val'), c.get('dev_poc'),
               p.get('dev_vah'), p.get('dev_val'), c.get('atr')) or c['atr'] <= 0:
        return None
    e, a = c['close'], c['atr']
    if p['close'] < p['dev_val'] and e > c['dev_val']:
        side, sgn = 'LONG', 1
    elif p['close'] > p['dev_vah'] and e < c['dev_vah']:
        side, sgn = 'SHORT', -1
    else:
        return None
    target = c['dev_poc']
    # A target already behind the entry carries no trade; reject rather than
    # silently flipping its direction.
    if (side == 'LONG' and target <= e) or (side == 'SHORT' and target >= e):
        return None
    return {'baseline': 'B2', 'side': side, 'entry': e,
            'stop': e - sgn * STOP_ATR * a, 'target': target,
            'exit_on_bias_neutral': False}


def b3_vwap_reclaim(h):
    """B3 - continuation. Session VWAP crossed with BIAS agreeing."""
    if len(h) < 2:
        return None
    c, p = h[-1], h[-2]
    if not _ok(c.get('vwap_sess'), p.get('vwap_sess'), c.get('bias'), c.get('atr')) \
       or c['atr'] <= 0:
        return None
    e, a = c['close'], c['atr']
    if p['close'] <= p['vwap_sess'] and e > c['vwap_sess'] and c['bias'] > 0:
        side, sgn, tgt = 'LONG', 1, c.get('band_u2')
    elif p['close'] >= p['vwap_sess'] and e < c['vwap_sess'] and c['bias'] < 0:
        side, sgn, tgt = 'SHORT', -1, c.get('band_l2')
    else:
        return None
    if tgt is None:
        return None
    if (side == 'LONG' and tgt <= e) or (side == 'SHORT' and tgt >= e):
        return None
    return {'baseline': 'B3', 'side': side, 'entry': e,
            'stop': e - sgn * STOP_ATR * a, 'target': tgt,
            'exit_on_bias_neutral': False}


BASELINES = {'B1': b1_bias_flip, 'B2': b2_va_return, 'B3': b3_vwap_reclaim}


def regime(h, lookback=20):
    """TREND / BALANCE / MIXED, from exportable data only, as of bar i."""
    if len(h) < lookback:
        return 'UNKNOWN', None, None
    win = h[-lookback:]
    usable = [r for r in win if _ok(r.get('vwap_sess'))]
    if len(usable) < lookback // 2:
        return 'UNKNOWN', None, None
    persistence = sum(1 for r in usable if r['close'] > r['vwap_sess']) / len(usable)

    c = h[-1]
    va_width = None
    if _ok(c.get('dev_vah'), c.get('dev_val'), c.get('atr')) and c['atr'] > 0:
        va_width = (c['dev_vah'] - c['dev_val']) / c['atr']

    if persistence >= 0.80 or persistence <= 0.20:
        reg = 'TREND'
    elif 0.35 <= persistence <= 0.65 and va_width is not None and va_width <= 4.0:
        reg = 'BALANCE'
    else:
        reg = 'MIXED'
    return reg, persistence, va_width


def ace_context(bias):
    """ACE's own strength bands, so the breakdown uses its thresholds not mine."""
    if bias is None:
        return 'UNKNOWN'
    b = abs(bias)
    if b < 0.15:
        return 'neutral'
    if b < 0.35:
        return 'weak'
    if b < 0.60:
        return 'moderate'
    return 'strong'


# ---------------------------------------------------------------------------
#  SCALP VARIANTS - symmetric 1:1 bracket
# ---------------------------------------------------------------------------
#  Same ACE entry logic as B1/B2/B3; only the exit changes. The target mirrors
#  the stop instead of coming from an ACE level, which has three consequences
#  worth stating rather than discovering later:
#
#   1. The "target already behind the entry" rejection in B2/B3 disappears,
#      because a mirrored target can never sit behind the entry. On the held-out
#      set that admits 42 more B2 and 14 more B3 signals, so the signal
#      population is NOT the same one B1/B2/B3 produce.
#   2. Outcomes become near-binary, +1R or -1R, which makes the permutation test
#      and the veto matrix read more cleanly than a spread of R multiples.
#   3. The pessimistic same-bar convention bites harder here. With stop and
#      target equidistant, a bar containing both is more likely than at 2:1, and
#      every such bar is scored as a loss. This is kept, not softened: intrabar
#      order is unknowable from OHLC and the alternative flatters the result.
#
#  The bias-neutral exit of B1 is dropped in the scalp variant so the bracket is
#  pure: stop, target, or the time stop. The originals are left untouched.

SCALP_STOP_ATR = 1.5      # unchanged from the frozen baselines
SCALP_RR       = 1.0      # target mirrors the stop


def _scalp(sig):
    if sig is None:
        return None
    e, sgn = sig['entry'], (1 if sig['side'] == 'LONG' else -1)
    risk = abs(e - sig['stop'])
    return {'baseline': sig['baseline'] + 's', 'side': sig['side'], 'entry': e,
            'stop': sig['stop'], 'target': e + sgn * SCALP_RR * risk,
            'exit_on_bias_neutral': False}


def b1s(h):
    return _scalp(b1_bias_flip(h))


def b2s(h):
    """B2 entry without the target-validity gate, which a 1:1 target makes moot."""
    if len(h) < 2:
        return None
    c, p = h[-1], h[-2]
    if not _ok(c.get('dev_vah'), c.get('dev_val'), p.get('dev_vah'),
               p.get('dev_val'), c.get('atr')) or c['atr'] <= 0:
        return None
    if p['close'] < p['dev_val'] and c['close'] > c['dev_val']:
        side, sgn = 'LONG', 1
    elif p['close'] > p['dev_vah'] and c['close'] < c['dev_vah']:
        side, sgn = 'SHORT', -1
    else:
        return None
    e, a = c['close'], c['atr']
    return _scalp({'baseline': 'B2', 'side': side, 'entry': e,
                   'stop': e - sgn * STOP_ATR * a, 'target': e + sgn * a})


def b3s(h):
    """B3 entry without the band-target gate, for the same reason."""
    if len(h) < 2:
        return None
    c, p = h[-1], h[-2]
    if not _ok(c.get('vwap_sess'), p.get('vwap_sess'), c.get('bias'), c.get('atr')) \
       or c['atr'] <= 0:
        return None
    if p['close'] <= p['vwap_sess'] and c['close'] > c['vwap_sess'] and c['bias'] > 0:
        side, sgn = 'LONG', 1
    elif p['close'] >= p['vwap_sess'] and c['close'] < c['vwap_sess'] and c['bias'] < 0:
        side, sgn = 'SHORT', -1
    else:
        return None
    e, a = c['close'], c['atr']
    return _scalp({'baseline': 'B3', 'side': side, 'entry': e,
                   'stop': e - sgn * STOP_ATR * a, 'target': e + sgn * a})


SCALP = {'B1s': b1s, 'B2s': b2s, 'B3s': b3s}
