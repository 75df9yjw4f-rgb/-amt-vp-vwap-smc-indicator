# Этап 3 — Архитектура индикатора

## 3.1. Общая форма

Один скрипт, Pine Script v6:

```pine
//@version=6
indicator("...", overlay = true,
     max_boxes_count     = 500,
     max_lines_count     = 500,
     max_labels_count    = 500,
     max_polylines_count = 100,
     max_bars_back       = 5000,
     scale               = scale.right)
```

Это `indicator`, а не `strategy`: мы не даём сигналов входа и не считаем доходность. Заявлять backtest-метрики на контекстном индикаторе — прямой путь к маркетинговому вранью, которого мы избегаем.

---

## 3.2. Модульная структура (порядок в файле = порядок вычислений)

```
┌──────────────────────────────────────────────────────────────────┐
│ 0. CONFIG            inputs, режимы, темы, дефолты               │
│ 1. CORE UTILS        UDT, хелперы, нормализация, guard-функции   │
│ 2. DATA LAYER        сессии, ATR, RVOL, Δ-proxy, LTF-мост        │
├──────────────────────────────────────────────────────────────────┤
│ 3. PROFILE ENGINE    бины, накопление, POC/VA/HVN/LVN            │  ← ядро
│ 4. AMT LAYER         IB, OR, balance, acceptance, initiative     │  ← поверх (3)
│ 5. VWAP ENGINE       session/period/anchored + σ-полосы          │  ← независим
│ 6. STRUCTURE ENGINE  свинги, HH/HL/LH/LL, BOS, CHoCH, MSS        │  ← независим
│ 7. LIQUIDITY ENGINE  EQH/EQL, пулы, sweep                        │  ← поверх (6)
│ 8. IMBALANCE ENGINE  FVG, displacement, OB                       │  ← поверх (6)
├──────────────────────────────────────────────────────────────────┤
│ 9. CONTEXT ENGINE    нормализация признаков → компонентные score │  ← читает 3–8
│10. SCORING           веса, агрегация, confidence, объяснения     │
│11. RENDER            polyline/box/line/label, гейтинг по режиму  │
│12. DASHBOARD         table, расшифровка каждого компонента       │
│13. ALERTS            alertcondition по FACT-событиям             │
└──────────────────────────────────────────────────────────────────┘
```

Жёсткое правило: **модули 3–8 производят только FACT** (числа и булевы факты о рынке). Ни один из них не решает «бычье это или медвежье». Вся интерпретация живёт исключительно в модулях 9–10. Это то самое разделение FACT / INTERPRETATION, и оно обеспечивается структурой кода, а не дисциплиной.

---

## 3.3. Типы данных (UDT)

```pine
type Profile
    float   lo              // нижняя граница сетки
    float   hi              // верхняя граница
    int     bins
    array<float> vol        // объём по бинам
    array<float> volUp      // Δ-proxy вверх
    array<float> volDn      // Δ-proxy вниз
    array<int>   tpo        // счётчик баров на цене (TPO)
    float   poc
    float   vah
    float   val
    float   total
    int     startBar
    int     endBar
    string  model           // "M1".."M4" — какая модель распределения фактически применена
    bool    ltfOk           // были ли доступны LTF-данные

type Swing
    float price
    int   bar
    bool  isHigh
    string label            // "HH" | "HL" | "LH" | "LL"

type Zone                   // общий тип для FVG / OB / ликвидности
    float top
    float bot
    int   startBar
    bool  bull
    int   kind              // 0=FVG 1=OB 2=LiqPool
    float mitigated         // 0.0 .. 1.0 — доля закрытия зоны
    box   bx
    line  ln

type Component              // элемент scoring-движка
    string name
    float  raw              // -1 .. +1
    float  weight
    bool   enabled
    bool   valid            // есть ли данные вообще
    int    barsSince        // возраст события (для затухания)
    string reason           // человекочитаемое объяснение
```

---

## 3.4. Data flow

```
                 ┌─────────────┐
   OHLCV ───────►│ DATA LAYER  │──► atr, rvol, deltaProxy, sessionId, isNewSession
                 └──────┬──────┘
                        │
        ┌───────────────┼────────────────┬──────────────────┐
        ▼               ▼                ▼                  ▼
 ┌─────────────┐ ┌─────────────┐  ┌─────────────┐   ┌──────────────┐
 │  PROFILE    │ │    VWAP     │  │  STRUCTURE  │   │  (LTF bridge)│
 │  ENGINE     │ │   ENGINE    │  │   ENGINE    │   │  опционально │
 └──────┬──────┘ └──────┬──────┘  └──────┬──────┘   └──────┬───────┘
        │               │                │                 │
   poc/vah/val      vwap/σ/z       swings/BOS/CHoCH    intrabar OHLCV
   hvn/lvn                               │                 │
   devPOC/devVA                          ├─────────┐       │
        │                                ▼         ▼       │
        │                        ┌────────────┐ ┌──────────────┐
        ├───────────────────────►│ LIQUIDITY  │ │  IMBALANCE   │
        ▼                        │ EQH/EQL    │ │ FVG/OB/displ │
 ┌─────────────┐                 │ sweep      │ └──────┬───────┘
 │  AMT LAYER  │                 └─────┬──────┘        │
 │ IB/OR       │                       │               │
 │ balance     │                       │               │
 │ acceptance  │                       │               │
 │ initiative  │                       │               │
 └──────┬──────┘                       │               │
        │                              │               │
        └──────────────┬───────────────┴───────────────┘
                       ▼
              ┌─────────────────┐
              │ CONTEXT ENGINE  │  каждый признак → Component(raw ∈ [-1,+1], reason)
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │    SCORING      │  bull / bear / net bias / confidence / Δ-объяснение
              └────────┬────────┘
                       ▼
         ┌─────────────┴─────────────┐
         ▼                           ▼
   ┌───────────┐              ┌─────────────┐
   │  RENDER   │              │  DASHBOARD  │
   └───────────┘              └─────────────┘
```

Никаких обратных связей: контекст не влияет на детекцию. Это гарантирует, что отключение любого визуального слоя не меняет расчёт, и что score воспроизводим.

---

## 3.5. Режимы производительности

| Параметр | **Lite** | **Standard** | **Pro** |
|---|---|---|---|
| Модель распределения объёма | M1 (close) | M3 (OHLC-weighted) | M4 (LTF) с fallback на M3 |
| Бинов в профиле | 24 | 50 | 100–500 |
| Профилей на графике | 1 (текущий) | 2 (текущий + предыдущий) | до 5 |
| Рендер профиля | выключен (только уровни) | боксы | polyline |
| Developing POC/VA | off | пересчёт раз в 5 баров | каждый бар |
| HVN / LVN | off | on | on + сила узла |
| Δ-proxy | по закрытию | по позиции закрытия | LTF-агрегация |
| Активных зон (FVG/OB/liq) | 10 | 25 | 50 |
| Rolling-lookback профиль | off | только на последнем баре | только на последнем баре |
| TPO-профиль | off | опционально | on |
| Ожидаемая нагрузка | минимальная | средняя | высокая (LTF — главный источник) |

Режим — единственный input, который меняет дефолты сразу нескольких подсистем; все отдельные переключатели остаются доступны и перекрывают режим.

---

## 3.6. Этап 9 — UI (структура настроек)

Группы inputs (`group=`), порядок сверху вниз, с `tooltip` на каждом неочевидном параметре.

**GENERAL**
`Performance Mode` (Lite/Standard/Pro) · `Theme` (Dark/Light/Auto) · `Confirm signals on bar close` (default ON) · `Show FACT layer` · `Show INTERPRETATION layer` · `Max historical bars to process`

**AUCTION / AMT**
`Profile anchor` (Session / Day / Week / Month / Fixed lookback / Visible range) · `Value Area %` (default 70) · `VA algorithm` (Classic pairwise / Sorted descending) · `Initial Balance minutes` (default 60) · `Show IB extensions` (1×/2×) · `Opening Range minutes` (default 15/30) · `Balance detection` (ATR-range / VA-overlap / Efficiency Ratio / Combined) · `Balance lookback` · `Balance threshold` · `Acceptance closes required` (default 2) · `Acceptance time %` (default 50) · `Rejection wick ratio` (default 0.6)

**VOLUME PROFILE**
`Bins` · `Distribution model` (Close / Uniform / OHLC-weighted / LTF) · `LTF resolution` (Auto / manual) · `Lookback bars` · `Profiles to show` · `Show POC / VAH / VAL` · `Show developing POC / VA` · `Developing recalc every N bars` · `Show HVN / LVN` · `HVN threshold` · `LVN threshold` · `Node detection window` · `Show TPO profile` · `Profile width %` · `Profile side` (Left/Right) · `Show volume histogram`

**VWAP**
`Session VWAP` · `Weekly VWAP` · `Monthly VWAP` · `Anchored VWAP #1..#3` с `Anchor mode` (Date / Session open / Highest high / Lowest low / Last swing high / Last swing low / Last BOS) и `Anchor date` · `Source` (hlc3 default) · `Bands` (on/off) · `Band multipliers` (1.0 / 2.0 / 3.0) · `Band mode` (Std.Dev / Percentage) · `Show price z-score vs VWAP`

**MARKET STRUCTURE**
`Swing length` (default 5) · `Structure confirmation` (Close / Wick) · `Show BOS` · `Show CHoCH` · `Show MSS` · `Show HH/HL/LH/LL labels` · `Internal structure` (короткая длина свинга, опционально) · `Show dealing range / Premium-Discount` · `Show EQ (50%)`

**LIQUIDITY**
`Show Equal Highs / Lows` · `EQH/EQL tolerance (×ATR)` (default 0.10) · `Max bars between equal points` · `Show liquidity pools` · `Include session/day/week highs-lows` · `Show sweeps` · `Sweep confirmation` (Close back inside / + CHoCH within N bars) · `Sweep lookahead bars`

**IMBALANCE**
`Show FVG` · `Min FVG size (×ATR)` · `FVG mitigation rule` (Touch / 50% / Full) · `Hide mitigated FVG` · `Show displacement` · `Displacement body (×ATR)` (default 1.5) · `Displacement requires FVG` · `Displacement requires volume` · `Show Order Blocks` · `OB rule` (Last opposite candle / Highest volume candle / Body threshold) · `OB zone` (Body / Full range) · `Max active zones`

**ORDER FLOW / VOLUME** *(только реально доступное)*
`Volume source check` (авто-отключение при отсутствии объёма) · `RVOL length` (default 20) · `RVOL confirm threshold` (default 1.5) · `Δ-proxy model` (Close direction / Close position / LTF) · `Show Δ-proxy in dashboard`

**CONTEXT ENGINE**
`Enable component: AMT / VP / VWAP / Structure / Liquidity / Imbalance / Volume` (7 чекбоксов) · `Weight: ...` (7 слайдеров) · `Event decay half-life (bars)` · `Neutral threshold` (0.15) · `Weak threshold` (0.35) · `Strong threshold` (0.60) · `Require minimum confidence` · `Show score history plot`

**DASHBOARD**
`Show dashboard` · `Position` (9 вариантов) · `Size` (Tiny/Small/Normal/Large) · `Show component breakdown` · `Show weights & contributions` · `Show reason column` · `Show «what changed» row` · `Show data-quality row` (модель VP, наличие объёма, LTF-статус)

---

## 3.7. Правила рендеринга (чтобы не упереться в лимиты)

1. Любой графический объект создаётся **один раз** и далее обновляется (`box.set_*`, `line.set_*`), а не пересоздаётся каждый бар.
2. Профиль в Pro рисуется **одной polyline** на профиль.
3. Зоны (FVG/OB/liq) живут в массиве с жёстким `maxZones`; при переполнении удаляется старейшая (`box.delete` обязателен, иначе утечка объектов).
4. Полностью митигированные зоны удаляются либо переводятся в «призрачный» стиль — по input.
5. Дашборд — одна `table`, обновляется только на `barstate.islast`.
6. Любые лейблы в истории — с гейтом `bar_index > last_bar_index - maxDrawBars`.
