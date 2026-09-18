//+------------------------------------------------------------------+
//|                                                   EmaCrossEA.mq5 |
//|                                                                  |
//| Opens a long position every time the fast EMA crosses above the   |
//| slow EMA. Lot size, stop loss, take profit, trading hours and     |
//| trading days are all adjustable from the inputs.                  |
//|                                                                  |
//| The cross is evaluated on CLOSED bars only. An EMA reading on the |
//| forming bar changes with every tick, so a signal taken from it    |
//| can appear and disappear within the same bar; the backtest would  |
//| show trades the live account could never have taken.              |
//+------------------------------------------------------------------+
#property copyright "EmaCrossEA"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\PositionInfo.mqh>

//--- signal -------------------------------------------------------------
input group                "Signal"
input ENUM_TIMEFRAMES      InpTimeframe      = PERIOD_CURRENT; // Timeframe the EMAs are read on
input int                  InpFastPeriod     = 40;             // Fast EMA period
input int                  InpSlowPeriod     = 200;            // Slow EMA period
input ENUM_APPLIED_PRICE   InpAppliedPrice   = PRICE_CLOSE;    // Applied price

//--- money --------------------------------------------------------------
input group                "Order"
input double               InpLots           = 0.5;            // Lot size
input double               InpStopLossPips   = 20.0;           // Stop loss (pips, 0 = none)
input double               InpTakeProfitPips = 40.0;           // Take profit (pips, 0 = none)
input int                  InpSlippage       = 10;             // Max deviation (points)
input long                 InpMagic          = 240401;         // Magic number
input string               InpComment        = "EmaCross";     // Order comment

//--- position control ---------------------------------------------------
input group                "Position control"
input bool                 InpAllowPyramiding = true;          // Allow a new trade while one is open
input int                  InpMaxPositions    = 0;             // Max simultaneous positions (0 = unlimited)
input double               InpMaxSpreadPips   = 0.0;           // Skip entry above this spread (0 = off)

//--- session ------------------------------------------------------------
input group                "Trading hours (server time)"
input bool                 InpUseTimeFilter  = true;           // Restrict trading to the session below
input int                  InpStartHour      = 8;              // Session start hour
input int                  InpStartMinute    = 0;              // Session start minute
input int                  InpEndHour        = 20;             // Session end hour
input int                  InpEndMinute      = 0;              // Session end minute

input group                "Trading days (server time)"
input bool                 InpMonday         = true;           // Monday
input bool                 InpTuesday        = true;           // Tuesday
input bool                 InpWednesday      = true;           // Wednesday
input bool                 InpThursday       = true;           // Thursday
input bool                 InpFriday         = true;           // Friday
input bool                 InpSaturday       = false;          // Saturday
input bool                 InpSunday         = false;          // Sunday

//--- globals ------------------------------------------------------------
CTrade         trade;
CSymbolInfo    sym;
CPositionInfo  pos;

int      hFast      = INVALID_HANDLE;
int      hSlow      = INVALID_HANDLE;
double   pipSize    = 0.0;
datetime lastBar    = 0;

//+------------------------------------------------------------------+
//| One pip in price terms.                                          |
//|                                                                  |
//| On a 5-digit EURUSD one point is 0.00001 and one pip is 0.0001;   |
//| on a 3-digit USDJPY one point is 0.001 and one pip is 0.01. Using |
//| points instead would make a "20 pip" stop ten times too tight.    |
//+------------------------------------------------------------------+
double PipSize()
{
   const int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   return (d == 3 || d == 5) ? point * 10.0 : point;
}

//+------------------------------------------------------------------+
//| Clamp a volume to the symbol's min / max / step.                 |
//+------------------------------------------------------------------+
double NormalizeVolume(const double volume)
{
   const double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double v = volume;
   if(vstep > 0.0)
      v = MathRound(v / vstep) * vstep;
   v = MathMax(vmin, MathMin(vmax, v));

   const int vdigits = (vstep > 0.0) ? (int)MathMax(0, -MathLog10(vstep) + 0.5) : 2;
   return NormalizeDouble(v, vdigits);
}

//+------------------------------------------------------------------+
//| True when now falls inside the configured session and weekday.   |
//| A session whose end is before its start is treated as spanning   |
//| midnight, so 22:00-06:00 works without extra inputs.             |
//+------------------------------------------------------------------+
bool DayEnabled(const int dayOfWeek)
{
   switch(dayOfWeek)
   {
      case 0: return InpSunday;
      case 1: return InpMonday;
      case 2: return InpTuesday;
      case 3: return InpWednesday;
      case 4: return InpThursday;
      case 5: return InpFriday;
      case 6: return InpSaturday;
   }
   return false;
}

bool SessionOpen()
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);

   if(!DayEnabled(t.day_of_week))
      return false;

   if(!InpUseTimeFilter)
      return true;

   const int now   = t.hour * 60 + t.min;
   const int start = InpStartHour * 60 + InpStartMinute;
   const int end   = InpEndHour   * 60 + InpEndMinute;

   if(start == end)
      return true;                       // a zero-length window means "all day"
   if(start < end)
      return (now >= start && now < end);
   return (now >= start || now < end);   // wraps past midnight
}

//+------------------------------------------------------------------+
//| Positions this EA owns on this symbol.                           |
//+------------------------------------------------------------------+
int OwnPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(pos.SelectByIndex(i))
         if(pos.Symbol() == _Symbol && pos.Magic() == InpMagic)
            n++;
   return n;
}

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpFastPeriod < 1 || InpSlowPeriod < 1)
   {
      Print("EmaCrossEA: EMA periods must be positive.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpFastPeriod >= InpSlowPeriod)
   {
      Print("EmaCrossEA: the fast EMA period must be smaller than the slow one.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpLots <= 0.0)
   {
      Print("EmaCrossEA: lot size must be positive.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpMaxPositions < 0)
   {
      Print("EmaCrossEA: max positions cannot be negative.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpStartHour < 0 || InpStartHour > 23 || InpEndHour < 0 || InpEndHour > 23 ||
      InpStartMinute < 0 || InpStartMinute > 59 || InpEndMinute < 0 || InpEndMinute > 59)
   {
      Print("EmaCrossEA: session hours must be 0-23 and minutes 0-59.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(!sym.Name(_Symbol))
   {
      Print("EmaCrossEA: cannot select symbol ", _Symbol);
      return INIT_FAILED;
   }

   hFast = iMA(_Symbol, InpTimeframe, InpFastPeriod, 0, MODE_EMA, InpAppliedPrice);
   hSlow = iMA(_Symbol, InpTimeframe, InpSlowPeriod, 0, MODE_EMA, InpAppliedPrice);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE)
   {
      Print("EmaCrossEA: failed to create the moving average handles, error ", GetLastError());
      return INIT_FAILED;
   }

   pipSize = PipSize();
   if(pipSize <= 0.0)
   {
      Print("EmaCrossEA: could not determine the pip size.");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber((ulong)InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);

   const double lots = NormalizeVolume(InpLots);
   if(MathAbs(lots - InpLots) > 1e-8)
      PrintFormat("EmaCrossEA: lot size %.4f adjusted to %.4f by the symbol's volume step.", InpLots, lots);

   // start from the next bar, so attaching the EA does not fire on a cross
   // that had already closed before it was loaded
   lastBar = iTime(_Symbol, InpTimeframe, 0);

   PrintFormat("EmaCrossEA started on %s, EMA %d/%d, %.2f lots, SL %.1f pips, TP %.1f pips, pip = %.*f",
               _Symbol, InpFastPeriod, InpSlowPeriod, lots,
               InpStopLossPips, InpTakeProfitPips, _Digits, pipSize);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hFast != INVALID_HANDLE) IndicatorRelease(hFast);
   if(hSlow != INVALID_HANDLE) IndicatorRelease(hSlow);
}

//+------------------------------------------------------------------+
//| A cross up on the last two closed bars.                          |
//+------------------------------------------------------------------+
bool CrossedUp()
{
   double fast[], slow[];
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);

   // index 1 is the last closed bar, index 2 the one before it
   if(CopyBuffer(hFast, 0, 1, 2, fast) != 2) return false;
   if(CopyBuffer(hSlow, 0, 1, 2, slow) != 2) return false;

   if(fast[0] == EMPTY_VALUE || slow[0] == EMPTY_VALUE ||
      fast[1] == EMPTY_VALUE || slow[1] == EMPTY_VALUE)
      return false;

   return (fast[1] <= slow[1] && fast[0] > slow[0]);
}

//+------------------------------------------------------------------+
//| Place the long order.                                            |
//+------------------------------------------------------------------+
bool OpenLong()
{
   if(!sym.RefreshRates())
   {
      Print("EmaCrossEA: no fresh quotes, entry skipped.");
      return false;
   }

   const double ask = sym.Ask();
   if(ask <= 0.0)
      return false;

   const double lots = NormalizeVolume(InpLots);

   double sl = (InpStopLossPips   > 0.0) ? ask - InpStopLossPips   * pipSize : 0.0;
   double tp = (InpTakeProfitPips > 0.0) ? ask + InpTakeProfitPips * pipSize : 0.0;

   // the broker refuses stops closer than SYMBOL_TRADE_STOPS_LEVEL
   const double point = sym.Point();
   const double minDist = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   if(minDist > 0.0)
   {
      if(sl > 0.0 && (ask - sl) < minDist) sl = ask - minDist;
      if(tp > 0.0 && (tp - ask) < minDist) tp = ask + minDist;
   }

   if(sl > 0.0) sl = NormalizeDouble(sl, _Digits);
   if(tp > 0.0) tp = NormalizeDouble(tp, _Digits);

   double margin = 0.0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lots, ask, margin))
   {
      if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
      {
         PrintFormat("EmaCrossEA: not enough free margin for %.2f lots (need %.2f).", lots, margin);
         return false;
      }
   }

   if(!trade.Buy(lots, _Symbol, 0.0, sl, tp, InpComment))
   {
      PrintFormat("EmaCrossEA: buy failed, retcode %d (%s), error %d.",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription(), GetLastError());
      return false;
   }

   PrintFormat("EmaCrossEA: long %.2f lots at %.*f, SL %.*f, TP %.*f, ticket %I64u.",
               lots, _Digits, trade.ResultPrice(), _Digits, sl, _Digits, tp, trade.ResultOrder());
   return true;
}

//+------------------------------------------------------------------+
//| Tick                                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // act once per closed bar
   const datetime barTime = iTime(_Symbol, InpTimeframe, 0);
   if(barTime == 0 || barTime == lastBar)
      return;
   lastBar = barTime;

   if(!SessionOpen())
      return;

   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ||
      !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
      !AccountInfoInteger(ACCOUNT_TRADE_EXPERT) ||
      !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))
      return;

   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL)
      return;

   const int open = OwnPositions();
   if(!InpAllowPyramiding && open > 0)
      return;
   if(InpMaxPositions > 0 && open >= InpMaxPositions)
      return;

   if(InpMaxSpreadPips > 0.0)
   {
      const double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) -
                             SymbolInfoDouble(_Symbol, SYMBOL_BID)) / pipSize;
      if(spread > InpMaxSpreadPips)
      {
         PrintFormat("EmaCrossEA: spread %.1f pips above the %.1f limit, entry skipped.",
                     spread, InpMaxSpreadPips);
         return;
      }
   }

   if(CrossedUp())
      OpenLong();
}
//+------------------------------------------------------------------+
