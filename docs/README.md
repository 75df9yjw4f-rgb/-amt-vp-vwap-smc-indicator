# Auction Context Engine — проектная документация

Индикатор для TradingView (Pine Script v6), объединяющий Auction Market Theory,
Volume Profile, VWAP и базовый Market Structure / SMC в **единый контекстный движок**.

Это **decision-support**, а не сигнальный индикатор: он описывает состояние аукциона
и объясняет, почему он его так описывает. Он не выдаёт BUY/SELL и не заявляет точность.

## Документы

| Файл | Содержание |
|---|---|
| `01-feasibility.md` | Этап 1: что возможно в Pine, лимиты платформы, итоговый verdict 🟢/🟡/🔴 |
| `02-licensing.md` | Этап 2: анализ лицензий чужого кода, почему пишем с нуля |
| `03-architecture.md` | Этап 3 + 9: модули, data flow, UDT, режимы Lite/Standard/Pro, UI |
| `04-algorithms.md` | Алгоритмические определения всех понятий (AMT, VP, VWAP, SMC) |
| `05-scoring.md` | Этапы 4–6: контекстный движок, scoring, дашборд |
| `06-repainting.md` | Этап 7: полный аудит repaint / lag / backpainting по каждому сигналу |
| `07-performance-and-roadmap.md` | Этапы 8, 10, 11: производительность, названия, план разработки |
| `08-footprint.md` | **Проверка `request.footprint()`** по актуальной документации — отменяет часть 🔴-вердиктов |
| `P0-acceptance.md` | Отчёт и критерии приёмки фазы P0 |
| `P1-acceptance.md` | Отчёт и критерии приёмки фазы P1 + протокол сравнения с нативным VP |
| `P3-acceptance.md` | Отчёт и критерии приёмки фазы P3 (VWAP) |
| `P5-acceptance.md` | Отчёт и критерии приёмки фазы P5 (Structure) + pivot-lag и repaint-аудит |
| `P6-acceptance.md` | Отчёт и критерии приёмки фазы P6 (Liquidity + Imbalance) + performance-аудит |

## Статус

✅ **P0** каркас · ✅ **P1** Profile · ✅ **P3** VWAP · ✅ **P5** Structure ·
✅ **P6** Liquidity + Imbalance (v0.5.0-P6).
⏳ Ожидается подтверждение перед **P7 (Volume / Order Flow + LTF + footprint)**.

Активных компонентов scoring: **5 из 7** (Volume Profile, VWAP, Structure, Liquidity, Imbalance).
Остальные честно показывают `NO DATA` с указанием причины, а не нейтральный ноль.

### Сборка (вариант B)
```bash
python3 tools/build.py          # -> build/ACE.pine (STD), build/ACE-Pro.pine (PRO)
python3 tools/build.py --check  # проверить синхронность с src/
```
`build/ACE.pine` не содержит `request.footprint()` и работает на любом тарифе.
`build/ACE-Pro.pine` требует Premium/Ultimate.

> ⚠️ Критерий «компилируется без ошибок» проверяется только в Pine Editor —
> офлайн-компилятора Pine Script не существует. См. `P0-acceptance.md`.

## Лицензия

Планируемая лицензия проекта: MPL-2.0. Весь код — оригинальный, сторонние
Pine-скрипты не заимствуются (обоснование в `02-licensing.md`).
