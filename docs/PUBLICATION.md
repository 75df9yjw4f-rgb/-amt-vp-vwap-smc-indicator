# P12 — Материалы для публикации

Тексты ниже — на английском, потому что описание публикации на TradingView должно быть на английском (House Rules). Копируются как есть, кроме отмеченных плейсхолдеров.

---

## 1. Перед публикацией — обязательные подстановки

| Где | Что заменить |
|---|---|
| `src/ACE.pine`, строка 5 | `© REPLACE_WITH_YOUR_TRADINGVIEW_USERNAME` → ваше имя аккаунта |
| Пересобрать | `python3 tools/build.py` — иначе плейсхолдер уедет в билды |

---

## 2. Описание — ACE (Standard build)

**Title:** `Auction Context Engine (ACE)`
**Short title:** `ACE`
**Category:** Volume, Trend Analysis
**Source:** `build/ACE.pine`

> ### Auction Context Engine — AMT · Volume Profile · VWAP · Market Structure
>
> **What this is:** a market-context tool. It measures where price sits relative to value, structure, liquidity and flow, combines those measurements into a single readable bias, and shows its full arithmetic so you can disagree with any part of it.
>
> **What this is not:** a signal generator. There is no BUY or SELL output, no arrows, no win rate, and no claim about future prices. Every number it shows is a description of what already happened.
>
> ---
>
> #### Seven engines, one context
>
> **Volume Profile** — price-binned volume distribution with POC, Value Area (classic CBOT pairwise expansion from the POC, or a sorted-threshold variant), VAH/VAL, HVN/LVN nodes, developing POC/VA, current and previous period profiles, and a TPO time-at-price mode that works on instruments with no volume at all.
>
> The grid uses a bin width fixed when the period opens. When price leaves the grid it is extended with empty bins rather than rebuilt, so existing bins keep their exact contents and no rounding error accumulates. Each bar contributes once.
>
> **VWAP** — session, daily, weekly and monthly anchors plus two independent Anchored VWAPs (date, session/week/month/year open, highest high, lowest low, last swing high/low, last structure break). Deviation bands are built from accumulated weighted moments — `sqrt(sumP2V/sumV − vwap²)` — not from squared deviations around a running mean, which understates band width because early bars get measured against a mean that no longer exists.
>
> **Market Structure** — swings via pivots, HH/HL/LH/LL sequencing, pending structure levels, and BOS / CHoCH / MSS. BOS is a break along the current structure direction, CHoCH is a break against it, MSS is a CHoCH carried by a displacement bar. Dealing range with equilibrium and premium/discount.
>
> **Liquidity** — swing-derived levels that merge within tolerance into equal highs/lows with a touch count, prior-day extremes, and sweep detection. The base sweep rule reads a single bar: price traded through the level and closed back. An optional mode holds the sweep pending until a structure event confirms it, or drops it when the window expires.
>
> **Imbalance** — three-bar Fair Value Gaps with a size filter, monotonic mitigation tracking, and Touch / 50% / Full closure rules.
>
> **Order flow** — relative volume, session cumulative directional volume, and a price/flow divergence check.
>
> **Auction Market Theory** — Initial Balance and Opening Range with extensions, three competing balance definitions (ATR range, value-area overlap, Kaufman efficiency ratio, with a 2-of-3 default), balance-to-imbalance transition, acceptance and rejection against a selectable reference, Dalton's initiative vs responsive activity measured against the previous value area, and a four-way open-type classification.
>
> ---
>
> #### Bias and confidence are two different things
>
> Each engine emits measurements and which side of the market they belong to. It does not decide whether that is bullish. The sign conventions live in one place, the Context Engine, where you can see and reweight them.
>
> ```
> bias      = Σ(weight × score) / Σ(weight)     over components that HAVE DATA
> coverage  = components with data / components enabled
> agreement = |Σ w·s| / Σ w·|s|
> strength  = Σ w·|s| / Σ w
> confidence = coverage × agreement × strength
> ```
>
> `bias` is direction and magnitude. `confidence` is **how internally consistent the model is** — it is not a probability that price will move. Six components agreeing at +0.8 and six fighting to +0.8 are different states, and one number cannot say so, which is why there are two.
>
> Because the denominator only counts components that have data, turning a component off does not drag the bias toward zero, and **no data is never treated as neutral**. A component with nothing to report says so, with the reason.
>
> ---
>
> #### It explains itself
>
> The dashboard shows every component's state, raw score, weight and contribution. A `WHAT CHANGED` row names the two components that moved the bias since the last closed bar, and reports a component gaining or losing data first — because that changes the denominator and can move the bias without any component's own reading having changed.
>
> Hover a component name for the reason behind its score. Bias, confidence, bull and bear are also in the Data Window for exact per-bar values.
>
> ---
>
> #### Honesty about timing
>
> Four different things get confused under the word "repainting", so they are separated here:
>
> - **Repainting** — a closed bar's value changing retroactively. **There is none.** No lookahead, no future references, no offset series, no `varip`.
> - **Lag** — a value that is correct but arrives late. Swings are confirmed `Swing length` bars after they occur, and everything derived from them inherits that: HH/HL/LH/LL, structure levels, the levels that BOS/CHoCH/MSS break, liquidity levels, equal highs/lows. The break itself is detected in real time on the bar's close; it is the **level** that arrives late. Turn on `Mark actual detection bar` to see the real delay on the chart.
> - **Backpainting** — a drawing placed on a past bar once the condition became known. Swing labels, order-flow-independent structure lines and confirmed sweep markers do this. It is geometrically correct and visually flattering, so it is listed rather than hidden.
> - **Source drift** — a closed bar's value differing after a chart reload because the **data provider** changed granularity. This affects lower-timeframe data. Components fed by it are marked with `~` and the data tier is always shown.
>
> Signals are confirmed on bar close by default.
>
> ---
>
> #### Data tiers, never conflated
>
> The dashboard always reports the tier actually used, never the one requested:
>
> - **BAR** — one OHLCV bar distributed by model. Always available.
> - **LTF** — lower-timeframe intrabars, classified by where each closed in its own range. Every plan; intrabar history depth is limited, so older bars fall back to BAR.
>
> Directional volume at these tiers is a **proxy**, labelled as such everywhere. True bid/ask aggressor delta is not available in Pine Script on any plan, and nothing here pretends otherwise.
>
> ---
>
> #### Performance modes
>
> `Performance Mode` caps the bin count, the number of profiles, the number of active zones and how often the profile is recomputed. It does **not** change the distribution model, the data source or what is drawn — those are separate switches, and they are what dominates the load. For the lightest setup use `Lite` together with `Profile data source = L1`.
>
> Measured on a synthetic reference: the distribution model drives accuracy far more than the bin count, and recomputing every bar instead of every fifth buys effectively nothing.
>
> ---
>
> #### Notes
>
> - Instruments without volume automatically fall back to a TPO time-at-price profile; the volume-dependent components report no data rather than degrading silently.
> - 28 alerts, all on objective events. There is deliberately no alert on the context, bias or confidence: those depend on weights you set, so an alert on them would deliver a tunable opinion dressed as an event.
> - Order blocks, breakers, mitigation blocks and inducement are intentionally **not** included.
> - Open-source under MPL-2.0. All code is original; no third-party Pine Script was used.
>
> **This is a decision-support tool, not financial advice. It describes the auction; what you do about it is your decision and your risk.**

---

## 3. Описание — ACE Pro build

**Title:** `Auction Context Engine Pro (ACE Pro)`
**Source:** `build/ACE-Pro.pine`

Текст идентичен разделу 2, со следующими изменениями:

**(а) Добавить в самое начало описания:**

> ⚠️ **Requires a TradingView Premium or Ultimate plan.** This build calls `request.footprint()`, and accounts below Premium cannot run scripts that request volume footprint data — it will not load. If you are on another plan, use the standard build of this script instead, which has identical logic minus the footprint tier.

**(б) Заменить раздел «Data tiers» на:**

> #### Data tiers, never conflated
>
> The dashboard always reports the tier actually used, never the one requested:
>
> - **FOOTPRINT** — `request.footprint()`. TradingView splits volume into buy and sell server-side, from data as fine as one tick. Gives per-row buy/sell volume, delta, volume imbalances, imbalance stacks and unfinished auction detection.
> - **LTF** — lower-timeframe intrabars, classified by where each closed in its own range.
> - **BAR** — one OHLCV bar distributed by model.
>
> **Important, and stated plainly:** footprint buy/sell volume is classified by **intrabar price direction**, not by bid/ask aggressor. It is the best classification available in Pine Script and it is still not order flow off the book. The dashboard labels it accordingly and never calls the lower tiers "delta" without the word "proxy".
>
> Footprint data is subject to source drift: TradingView builds it from progressively coarser intrabar intervals as bars age, so closed-bar values can differ after a reload. Components fed by it carry a `~` mark.

---

## 4. Чек-лист соответствия House Rules TradingView

| Правило | Как выполнено |
|---|---|
| Описание на английском | ✅ разделы 2–3 |
| Описание объясняет, **что** делает скрипт | ✅ семь движков, каждый с определением |
| Описание объясняет, **как** он это делает | ✅ формулы bias/confidence, алгоритм Value Area, накопление моментов VWAP |
| Оригинальность / существенная доработка | ✅ весь код с нуля; `ATTRIBUTION.md` |
| Кредит авторам переиспользованного кода | ✅ н/п — заимствований нет |
| Открытая публикация при использовании чужого открытого кода | ✅ н/п; публикуем открыто в любом случае |
| Отсутствие обещаний прибыли и точности | ✅ автоматический скан кода и документации — 6 совпадений, все отрицания или проценты бюджета |
| Отсутствие вводящих в заблуждение заявлений | ✅ разделы про repaint/lag/backpainting/source drift и про то, что footprint ≠ bid/ask |
| Нет рекламы платных услуг и внешних ссылок на них | ✅ ссылок нет вовсе |
| Нет чужих брендов и заявлений об аффилиации | ✅ `ATTRIBUTION.md`, «Товарные знаки» |
| Указание требований тарифа, если есть | ✅ PRO-билд, раздел 3(а) |
| Честное указание repainting-поведения | ✅ отдельный раздел описания + `REPAINT-TEST-REPORT.md` |
| Лицензия | ✅ MPL-2.0, `LICENSE` + Exhibit A в шапке скрипта |

---

## 5. Что остаётся вашим решением

1. **Имя аккаунта** в шапке — плейсхолдер намеренно виден, чтобы его нельзя было не заметить.
2. **Публиковать ли PRO-билд отдельно.** Он недоступен большинству пользователей; альтернатива — публиковать только Standard.
3. **Скриншот для публикации.** Рекомендую снимать в `Standard` на ликвидном фьючерсе или крипте с включённым дашбордом: он показывает и уровни, и разбивку score, и строку `DATA`.
4. **Порядок публикации.** Если публикуете оба, разумно сначала Standard, затем Pro со ссылкой на него как на базовую версию.
