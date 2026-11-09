#ifndef GOLDSHIELD_DOMAIN_TYPES_MQH
#define GOLDSHIELD_DOMAIN_TYPES_MQH

enum GSExecutionMode
  {
   DRY_RUN=0, SHADOW=1, RULES_DEMO=2,
   ONNX_DEMO=3, HYBRID_DEMO=4, REAL_RESTRICTED=5
  };
enum GSState
  {
   INIT, RECOVERY, READY, SIGNAL_PENDING, OPENING, BASKET_ACTIVE,
   BASKET_EXITING, COOLDOWN, PAUSED_MANUAL, PAUSED_RISK,
   PAUSED_VOLATILITY, SAFE_MODE, ERROR_BLOCKED
  };
enum GSSide { GS_HOLD=0, GS_BUY=1, GS_SELL=-1 };
enum GSSignalModel { GS_BASELINE=0, GS_TREND_PULLBACK=1 };

struct GSMarketSnapshot
  {
   MqlRates bar;
   MqlRates previous;
   datetime available_at_server;
   double fast_ema;
   double slow_ema;
   double rsi;
   double atr;
   double adx;
   double previous_adx;
   double avg_tick_volume;
   double breakout_high;
   double breakout_low;
   double previous_fast_ema;
   double previous_slow_ema;
   double trend_close;
   double trend_fast_ema;
   double trend_slow_ema;
   double previous_trend_fast_ema;
   datetime trend_available_at_server;
  };
struct GSTradePlan
  {
   GSSide side;
   datetime candle_id;
   double entry;
   double sl;
   double tp;
   double volume;
   double risk_budget;
   double estimated_loss;
   double estimated_margin;
   ENUM_ORDER_TYPE_FILLING filling;
   string comment;
  };
struct GSOwnedPosition
  {
   int count;
   int pending_orders;
   bool collision;
   ulong ticket;
   long identifier;
   long direction;
   double volume;
   double sl;
   double floating_pl; // Profit + swap; commission not included.
   datetime opened_at;
   string comment;
  };

bool GSReject(string &reason,const string code)
  {
   reason=code;
   return false;
  }
#endif
