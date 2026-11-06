#ifndef GOLDSHIELD_RULE_SIGNAL_MQH
#define GOLDSHIELD_RULE_SIGNAL_MQH
#include <GoldShieldDemo20/DomainTypes.mqh>
#include <GoldShieldDemo20/Settings.mqh>

GSSide GSEvaluateRules(const GSMarketSnapshot &data,const MqlTick &tick,string &reason)
  {
   if(TimeCurrent()<data.available_at_server ||
      TimeCurrent()-data.available_at_server>MaxSignalAgeSeconds)
     { reason="HOLD_SIGNAL_TOO_OLD_OR_CLOCK"; return GS_HOLD; }
   if(data.bar.high-data.bar.low>data.atr*MaxCandleATRMultiple ||
      MathAbs(data.bar.open-data.previous.close)>data.atr*MaxGapATRMultiple ||
      MathAbs(tick.bid-data.bar.close)>data.atr*MaxGapATRMultiple)
     { reason="HOLD_VOLATILITY_OR_GAP"; return GS_HOLD; }
   int side=GSBaselineSide(data.bar.close,data.fast_ema,data.slow_ema,data.rsi,UseRSIFilter);
   if(side!=0 && SignalModel==GS_TREND_PULLBACK)
     {
      if(!GSTrendPullbackOK(side,data.bar.open,data.bar.close,data.previous.high,data.previous.low,
                           data.previous_fast_ema,data.fast_ema,data.slow_ema,data.previous_slow_ema,
                           data.trend_close,data.trend_fast_ema,data.trend_slow_ema,data.atr,MaxEntryStretchATR))
        { reason="HOLD_TREND_PULLBACK_NOT_CONFIRMED"; return GS_HOLD; }
      reason="CANDIDATE_CONFIRMED_TREND_PULLBACK";
      return (GSSide)side;
     }
   reason=(side==0 ? "HOLD_RULES_NO_SETUP" : "CANDIDATE_BASELINE_EMA_RSI");
   return (GSSide)side;
  }
#endif
