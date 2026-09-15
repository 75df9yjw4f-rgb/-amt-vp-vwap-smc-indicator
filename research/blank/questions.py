"""Answers to the ten questions listed in docs/23, plus the controls needed to
tell whether EARLY is a cause or a restatement of "this trade lost".
"""
import json, statistics, math, random
t = json.load(open('research/blank/classified.json'))
L = [x for x in t if x['r'] < 0]; W = [x for x in t if x['r'] > 0]

def ci(rs, n=10000):
    random.seed(7); m = []
    for _ in range(n):
        m.append(statistics.mean(random.choices(rs, k=len(rs))))
    m.sort(); return m[int(.025*n)], m[int(.975*n)]

rs = [x['r'] for x in t]
lo, hi = ci(rs)
print(f"1. Итог: {sum(rs):+.1f}R за {len(t)} сделок, ожидание {statistics.mean(rs):+.3f}R, 95% CI [{lo:+.3f}, {hi:+.3f}]")
print(f"   побед {len(W)}/{len(t)} = {len(W)/len(t):.1%}; для 1:1 безубыток = 50%")

# 2. direction
for d in ('LONG','SHORT'):
    g=[x for x in t if x['decision']==d]
    if g: print(f"2. {d:<5s} n={len(g):3d} exp {statistics.mean(y['r'] for y in g):+.3f}R  побед {sum(1 for y in g if y['r']>0)/len(g):.0%}")

# 3. time / session
print("3. по часам UTC:")
by={}
for x in t: by.setdefault(x['f']['hour_utc']//4*4,[]).append(x['r'])
for k in sorted(by): print(f"   {k:02d}-{k+3:02d}h n={len(by[k]):3d} exp {statistics.mean(by[k]):+.3f}R")

# 4. exits
print("4. выходы:", {o: sum(1 for x in t if x['outcome']==o) for o in ('TARGET','STOP','TIME')})
print(f"   средняя длительность: победы {statistics.mean(x['bars'] for x in W):.1f} баров, убытки {statistics.mean(x['bars'] for x in L):.1f}")

# 5. MFE of losers
print(f"5. MFE убыточных: медиана {statistics.median(x['mfe'] for x in L):.2f}R, "
      f"доля с MFE>=0.5R {sum(1 for x in L if x['mfe']>=0.5)/len(L):.0%}, >=0.8R {sum(1 for x in L if x['mfe']>=0.8)/len(L):.0%}")
print(f"   MAE прибыльных: медиана {statistics.median(x['mae'] for x in W):.2f}R, доля с MAE>=0.5R {sum(1 for x in W if x['mae']>=0.5)/len(W):.0%}")

# 6. is EARLY predictable at entry? -> cause vs restatement
print("6. предсказуем ли EARLY по признакам ВХОДА:")
E=[x for x in t if 'EARLY' in x['cats']]; NE=[x for x in t if 'EARLY' not in x['cats']]
for k in ('range_vs_med100','realized_vol_20','bar_pos','range_60_vs_med'):
    a=statistics.mean(x['f'][k] for x in E); c=statistics.mean(x['f'][k] for x in NE)
    print(f"   {k:<18s} EARLY {a:6.2f}   не-EARLY {c:6.2f}   разница {a-c:+.2f}")
run=lambda x: abs(x['f']['net_move_60'])/x['f']['range_60_vs_med'] if x['f']['range_60_vs_med'] else 0
print(f"   run60              EARLY {statistics.mean(map(run,E)):6.2f}   не-EARLY {statistics.mean(map(run,NE)):6.2f}")

# 7. does the run60 HOLD filter earn its keep? (HOLDs were not simulated -> state only)
print(f"7. HOLD по run60>0.6: {sum(1 for x in json.load(open('research/blank/state.json'))['trades'] if x['decision']=='HOLD')} штук — исходы не измерялись (правило заморожено до прогона)")

# 8. streaks
seq=''.join('W' if x['r']>0 else 'L' for x in t)
import re
mx=max(len(m) for m in re.findall(r'L+',seq)); mw=max(len(m) for m in re.findall(r'W+',seq))
print(f"8. макс серия убытков {mx}, макс серия побед {mw}; последовательность: {seq}")

# 9. first half vs second half
h=len(t)//2
print(f"9. первая половина exp {statistics.mean(x['r'] for x in t[:h]):+.3f}R, вторая {statistics.mean(x['r'] for x in t[h:]):+.3f}R  (обучения по журналу не видно/видно)")

# 10. spread
print("10. спред 0.30 пункта против стопа ~0.15% цены:")
sp=[0.30/(x['f'].get('entry_price') or 0) for x in t if x['f'].get('entry_price')]
print(f"    стоп в пунктах ~ 0.0015*цена; при цене ~3300 это ~4.95 пункта -> спред 0.30 = {0.30/4.95:.1%} стопа = {-0.30/4.95:.3f}R на сделку")
print(f"    ожидание с учётом спреда: {statistics.mean(rs)-0.30/4.95:+.3f}R")
