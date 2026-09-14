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
| `P7-acceptance.md` | Фаза P7 (Volume / Order Flow) + аудит footprint, тарифов, realtime/history, repaint, performance |
| `P4-acceptance.md` | Фаза P4 (AMT) + аудит взаимодействия движков, scoring, repaint, performance |
| `P8-acceptance.md` | Фаза P8 (Change Explanation) + аудит scoring и корреляции, зафиксированный scope v1 |
| `P9-acceptance.md` | Фаза P9 (Alerts) + аудит инертных input'ов, repaint и performance |
| `REPAINT-TEST-REPORT.md` | **P10** — полный repaint-аудит P1–P9, performance-аудит, процедура ручной проверки |
| `P11-acceptance.md` | Фаза P11 (профилирование и режимы) + измеренное сравнение Lite/Standard/Pro |
| `P12-acceptance.md` | Фаза P12 (публикация) + финальный аудит и сводные Known Limitations |
| `PUBLICATION.md` | Тексты описаний для TradingView + чек-лист House Rules |
| `ATTRIBUTION.md` | Реестр заимствований (их нет) и источники знаний |

## Статус

✅ **P0** каркас · ✅ **P1** Profile · ✅ **P3** VWAP · ✅ **P5** Structure ·
✅ **P6** Liquidity + Imbalance · ✅ **P7** Volume / Order Flow · ✅ **P4** AMT (v0.7.0-P4).

**Все семь движков реализованы.** Активных компонентов scoring: **7 из 7**
на интрадей-инструменте с объёмом.

✅ **P8** Change Explanation · ✅ **P9** Alerts (v0.9.0-P9) ·
✅ **P10** Repaint-аудит · ✅ **P11** Профилирование и режимы ·
✅ **P12** Публикация — **v1.0.0-rc**.

🏁 **Все фазы roadmap завершены.** Перед публикацией: заменить плейсхолдер
копирайта, пересобрать, прогнать компиляцию и графические тесты в Pine Editor.

Дефект Lite из P10 исправлен и проверен измерением (`tools/profile_sim.py`):
`Profile.ready` наступает на баре 0 вместо 299.

**Repaint отсутствует.** Задержки, backpainting и source drift разведены и
задокументированы в `REPAINT-TEST-REPORT.md`. Там же — находка аудита о
децимации developing-профиля, которая должна стать первым пунктом P11.

28 `alertcondition` — **только по FACT-событиям**. Алерта на контекст, bias
и confidence нет сознательно: они зависят от пользовательских весов.

### Scope ACE v1 — зафиксирован
Order Blocks, Breakers, Mitigation Blocks, Inducement и прочие расширенные
institutional/SMC-метки **не входят** в v1 и будут отдельным индикатором.
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
