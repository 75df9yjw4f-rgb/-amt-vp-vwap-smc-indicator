# EmaCrossEA

MQL5 expert advisor. Opens a long position every time the fast EMA crosses above
the slow EMA. Lot size, stop loss, take profit, trading hours and trading days
are all set from the inputs.

## Install

1. In MetaTrader 5: **File → Open Data Folder**, then `MQL5/Experts/`.
2. Copy `EmaCrossEA.mq5` there.
3. In MetaEditor press **F7** to compile (it has no external dependencies beyond
   the standard `Trade` library that ships with the terminal).
4. Drag the EA onto a chart and allow algorithmic trading.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `InpTimeframe` | current | Timeframe the EMAs are read on |
| `InpFastPeriod` | 40 | Fast EMA period |
| `InpSlowPeriod` | 200 | Slow EMA period |
| `InpAppliedPrice` | Close | Applied price for both EMAs |
| `InpLots` | 0.5 | Lot size |
| `InpStopLossPips` | 20 | Stop loss in pips (0 = none) |
| `InpTakeProfitPips` | 40 | Take profit in pips (0 = none) |
| `InpSlippage` | 10 | Max deviation in points |
| `InpMagic` | 240401 | Magic number; the EA only counts its own positions |
| `InpComment` | EmaCross | Order comment |
| `InpAllowPyramiding` | true | Allow a new trade while one is already open |
| `InpMaxPositions` | 0 | Cap on simultaneous positions, 0 = unlimited |
| `InpMaxSpreadPips` | 0 | Skip the entry above this spread, 0 = off |
| `InpUseTimeFilter` | true | Restrict trading to the session below |
| `InpStartHour` / `InpStartMinute` | 8:00 | Session start, **server time** |
| `InpEndHour` / `InpEndMinute` | 20:00 | Session end, **server time** |
| `InpMonday` … `InpSunday` | Mon–Fri on | Days the EA may open trades |

## Behaviour worth knowing before you run it

**The signal is taken on closed bars.** An EMA on the forming bar changes with
every tick, so a cross can appear and vanish inside the same bar. Reading index 1
and 2 means the backtest and the live account see the same signal.

**Pips, not points.** On a 5-digit EURUSD a pip is `10 * Point`, on a 3-digit
USDJPY likewise. A "20 pip" stop taken as 20 points would be ten times too tight;
the EA converts through `PipSize()`.

**Broker stop distance.** If the requested stop or target is closer than
`SYMBOL_TRADE_STOPS_LEVEL`, it is pushed out to the minimum the broker accepts
rather than letting the order be rejected.

**Session times are server time**, not your local clock. Check the broker's
offset before setting the hours. A session whose end is earlier than its start
is treated as spanning midnight, so `22:00 → 06:00` works as written.

**Every cross opens a trade.** With `InpAllowPyramiding = true` (the default,
matching the specification) a new cross adds a position even if one is open. Set
it to false, or use `InpMaxPositions`, if you want one at a time.

**Exits are the stop and target only.** There is no exit on the opposite cross,
no trailing stop and no close at session end — nothing beyond what was asked for.
A position opened just before the session closes stays open until its stop or
target is hit.

## Before trading it with money

This EA does what the specification says; whether the specification makes money
is a separate question and this repository's `docs/` is largely a record of
similar rules failing once controls were applied. Run it in the Strategy Tester
on your own broker's data and spread first, over a period long enough to contain
more than one market regime, and compare it against simply holding the
instrument over the same window.
