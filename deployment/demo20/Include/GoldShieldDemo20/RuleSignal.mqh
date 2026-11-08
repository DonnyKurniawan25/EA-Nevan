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

   // Prioritas 2: Filter sideways / konsolidasi via ADX
   if(UseADXFilter)
     {
      if(!MathIsValidNumber(data.adx) || data.adx<0.0)
        { reason="HOLD_ADX_DATA_INVALID"; return GS_HOLD; }
      if(data.adx<ADXThreshold)
        { reason="HOLD_ADX_SIDEWAYS"; return GS_HOLD; }
     }

   int side=GSBaselineSide(data.bar.close,data.fast_ema,data.slow_ema,data.rsi,UseRSIFilter);

   if(side!=0 && RequireFreshCross)
     {
      bool fresh_buy=(data.previous_fast_ema<=data.previous_slow_ema && data.fast_ema>data.slow_ema) ||
                     (data.previous.close<=data.previous_fast_ema && data.bar.close>data.fast_ema);
      bool fresh_sell=(data.previous_fast_ema>=data.previous_slow_ema && data.fast_ema<data.slow_ema) ||
                      (data.previous.close>=data.previous_fast_ema && data.bar.close<data.fast_ema);
      if(side==1 && !fresh_buy)
        { reason="HOLD_NO_FRESH_TRIGGER"; return GS_HOLD; }
      if(side==-1 && !fresh_sell)
        { reason="HOLD_NO_FRESH_TRIGGER"; return GS_HOLD; }
     }

   // Prioritas 2: Multi-Timeframe Trend Filter (M15 + H1 EMA)
   if(side!=0 && UseHTFTrendFilter)
     {
      if(!GSPositive(data.trend_close) || !GSPositive(data.trend_fast_ema) || !GSPositive(data.trend_slow_ema))
        { reason="HOLD_HTF_DATA_INVALID"; return GS_HOLD; }
      if(side==1)
        {
         if(data.trend_close<data.trend_slow_ema || data.trend_fast_ema<data.trend_slow_ema)
           { reason="HOLD_HTF_TREND_BEARISH"; return GS_HOLD; }
        }
      else if(side==-1)
        {
         if(data.trend_close>data.trend_slow_ema || data.trend_fast_ema>data.trend_slow_ema)
           { reason="HOLD_HTF_TREND_BULLISH"; return GS_HOLD; }
        }
     }

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
