# Auction Context Engine (ACE)

TradingView-индикатор на Pine Script v6, объединяющий **Auction Market Theory, Volume Profile, VWAP, Market Structure, Liquidity, Imbalance и Order Flow** в один контекстный движок.

Это **decision-support**, а не сигнальный индикатор. Он не выдаёт BUY/SELL, не заявляет точность и не предсказывает цену. Он измеряет состояние аукциона и показывает всю арифметику, по которой пришёл к выводу.

---

## Сборка

Один источник, два билда:

```bash
python3 tools/build.py          # -> build/ACE.pine (STD), build/ACE-Pro.pine (PRO)
python3 tools/build.py --check  # проверить синхронность с src/ (для CI)
```

| Билд | Тариф | Источники данных |
|---|---|---|
| `build/ACE.pine` | **любой** | L0/L1 bar · L2 lower timeframe |
| `build/ACE-Pro.pine` | **Premium / Ultimate** | + L3 `request.footprint()` |

STD получается **удалением** изолированного региона `L3 FOOTPRINT ADAPTER`, а не правкой логики. Сборщик это проверяет: если footprint просочится в STD или исчезнет из PRO — сборка падает.

## Измерительный стенд

```bash
python3 tools/profile_sim.py    # точность и нагрузка Lite / Standard / Pro
```

## Принципы, заложенные в архитектуру

**FACT vs INTERPRETATION.** Движки выдают только измеримые величины и то, к какой стороне рынка они относятся. Знак вклада и итоговый контекст формируются в одном месте — Context Engine, где их видно и можно перевесить.

**NO DATA ≠ NEUTRAL.** Компонент без данных исключается из знаменателя, а не считается нейтральным нулём, и в дашборде указывает причину.

**Bias и Confidence — разные величины.** Confidence — это внутренняя согласованность модели, **не** вероятность движения цены.

**Честность по времени.** Repaint, lag, backpainting и source drift разведены и задокументированы по каждому сигналу. Repaint отсутствует; остальное описано, а не спрятано.

## Документация

| Файл | Содержание |
|---|---|
| [`docs/README.md`](docs/README.md) | указатель по всем документам |
| [`docs/01-feasibility.md`](docs/01-feasibility.md) | что возможно в Pine, лимиты платформы |
| [`docs/02-licensing.md`](docs/02-licensing.md) | анализ лицензий, почему код написан с нуля |
| [`docs/03-architecture.md`](docs/03-architecture.md) | модули, data flow, режимы, UI |
| [`docs/04-algorithms.md`](docs/04-algorithms.md) | алгоритмические определения всех понятий |
| [`docs/05-scoring.md`](docs/05-scoring.md) | scoring, confidence, дашборд |
| [`docs/06-repainting.md`](docs/06-repainting.md) | методология аудита repainting |
| [`docs/08-footprint.md`](docs/08-footprint.md) | проверка `request.footprint()` по документации |
| [`docs/REPAINT-TEST-REPORT.md`](docs/REPAINT-TEST-REPORT.md) | полный repaint-аудит P1–P9 |
| [`docs/PUBLICATION.md`](docs/PUBLICATION.md) | тексты для публикации и чек-лист House Rules |
| [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md) | заимствования: их нет |
| `docs/P*-acceptance.md` | отчёты и критерии приёмки по фазам |

## Scope v1

**Входит:** Volume Profile · VWAP · Market Structure · Liquidity · Imbalance (FVG) · Order Flow · AMT · Context/Scoring · Dashboard · Alerts.

**Не входит сознательно:** Order Blocks, Breakers, Mitigation Blocks, Inducement и прочие расширенные institutional/SMC-метки — отдельный индикатор.

## Лицензия

[MPL-2.0](LICENSE). Весь код оригинальный; сторонний Pine Script не заимствовался — см. [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md).

---

**Дисклеймер.** Индикатор описывает состояние аукциона. Он не является финансовой рекомендацией. Торговые решения и риск — ваши.
