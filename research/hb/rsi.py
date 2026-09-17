"""RSI and standard companions, on their textbook defaults.

Six variants, all declared in the ledger before the first run. No parameter is
swept: RSI 14 with 30/70, EMA 200, Bollinger 20/2, MACD 12/26/9, ADX 14 are the
defaults everyone uses. Testing six things at once costs significance, and that
cost is stated with the result rather than hidden by reporting the best one.
"""
import sys
sys.path.insert(0, '/home/user/hb-compat')
WARMUP = 300


def _frame(b):
    import pandas as pd
    return pd.DataFrame({'open': [x['o'] for x in b], 'high': [x['h'] for x in b],
                         'low': [x['l'] for x in b], 'close': [x['c'] for x in b]})


def indicators(b):
    import pandas_ta  # noqa: F401
    f = _frame(b)
    d = {'rsi': f.ta.rsi(length=14), 'ema200': f.ta.ema(length=200),
         'adx': f.ta.adx(length=14)['ADX_14']}
    bb = f.ta.bbands(length=20, std=2.0)
    d['bbl'] = bb['BBL_20_2.0']; d['bbu'] = bb['BBU_20_2.0']
    mac = f.ta.macd(fast=12, slow=26, signal=9)
    d['hist'] = mac['MACDh_12_26_9']
    return d


def signals(b, variant):
    d = indicators(b)
    r, e, adx, bbl, bbu, h = d['rsi'], d['ema200'], d['adx'], d['bbl'], d['bbu'], d['hist']
    out = {}
    for i in range(WARMUP, len(b) - 1):
        c, pc = b[i]['c'], b[i - 1]['c']
        ri, rp = r.iloc[i], r.iloc[i - 1]
        if ri != ri or rp != rp:
            continue
        long = short = False
        if variant == 'V1':                      # classic oversold / overbought
            long, short = rp >= 30 > ri, rp <= 70 < ri
        elif variant == 'V2':                    # V1 with an EMA200 trend filter
            long = (rp >= 30 > ri) and c > e.iloc[i]
            short = (rp <= 70 < ri) and c < e.iloc[i]
        elif variant == 'V3':                    # RSI as momentum: the 50 line
            long, short = rp <= 50 < ri, rp >= 50 > ri
        elif variant == 'V4':                    # oversold AND outside the band
            long = ri < 30 and b[i]['c'] < bbl.iloc[i]
            short = ri > 70 and b[i]['c'] > bbu.iloc[i]
        elif variant == 'V5':                    # oversold AND MACD histogram turning up
            long = ri < 30 and h.iloc[i] > h.iloc[i - 1]
            short = ri > 70 and h.iloc[i] < h.iloc[i - 1]
        elif variant == 'V6':                    # V2 plus trend strength
            long = (rp >= 30 > ri) and c > e.iloc[i] and adx.iloc[i] > 20
            short = (rp <= 70 < ri) and c < e.iloc[i] and adx.iloc[i] > 20
        if long:
            out[i] = 'LONG'
        elif short:
            out[i] = 'SHORT'
    return out


VARIANTS = {'V1': 'RSI<30 → LONG, RSI>70 → SHORT',
            'V2': 'V1 + фильтр EMA200',
            'V3': 'RSI пересекает 50',
            'V4': 'RSI<30 и выход за полосу Боллинджера',
            'V5': 'RSI<30 и разворот гистограммы MACD',
            'V6': 'V2 + ADX>20'}
