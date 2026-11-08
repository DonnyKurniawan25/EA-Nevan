#ifndef GOLDSHIELD_MARKET_DATA_MQH
#define GOLDSHIELD_MARKET_DATA_MQH
#include <GoldShieldDemo20/DomainTypes.mqh>
#include <GoldShieldDemo20/SafetyMath.mqh>

class GSMarketData
  {
private:
   int m_fast,m_slow,m_rsi,m_atr;
   int m_adx;
   int m_trend_fast,m_trend_slow;
   bool m_confirm;
   bool m_use_adx;
   ENUM_TIMEFRAMES m_trend_timeframe;
   string m_symbol;
   ENUM_TIMEFRAMES m_timeframe;
   bool ReadValue(const int handle,double &value)
     {
      double buffer[1];
      if(CopyBuffer(handle,0,1,1,buffer)!=1) return false; // shift 1: closed bar only.
      value=buffer[0];
      return MathIsValidNumber(value) && value!=EMPTY_VALUE;
     }
   bool ReadPrevious(const int handle,double &value)
     {
      double buffer[1];
      if(CopyBuffer(handle,0,2,1,buffer)!=1) return false;
      value=buffer[0];
      return GSPositive(value) && value!=EMPTY_VALUE;
     }
public:
   GSMarketData(void)
     {
      m_fast=INVALID_HANDLE; m_slow=INVALID_HANDLE; m_rsi=INVALID_HANDLE; m_atr=INVALID_HANDLE;
      m_adx=INVALID_HANDLE;
      m_trend_fast=INVALID_HANDLE; m_trend_slow=INVALID_HANDLE; m_confirm=false; m_use_adx=false;
     }
   bool Init(const string symbol,const ENUM_TIMEFRAMES timeframe,
             const int fast,const int slow,const int rsi,const int atr,
             const bool confirm,const ENUM_TIMEFRAMES trend_timeframe,
             const bool use_adx=false,const int adx_period=14)
     {
      m_symbol=symbol; m_timeframe=timeframe;
      m_confirm=confirm; m_trend_timeframe=trend_timeframe;
      m_use_adx=use_adx;
      m_fast=iMA(symbol,timeframe,fast,0,MODE_EMA,PRICE_CLOSE);
      m_slow=iMA(symbol,timeframe,slow,0,MODE_EMA,PRICE_CLOSE);
      m_rsi=iRSI(symbol,timeframe,rsi,PRICE_CLOSE);
      m_atr=iATR(symbol,timeframe,atr);
      if(m_use_adx)
        {
         m_adx=iADX(symbol,timeframe,adx_period);
         if(m_adx==INVALID_HANDLE) return false;
        }
      if(m_confirm)
        {
         m_trend_fast=iMA(symbol,trend_timeframe,fast,0,MODE_EMA,PRICE_CLOSE);
         m_trend_slow=iMA(symbol,trend_timeframe,slow,0,MODE_EMA,PRICE_CLOSE);
         if(m_trend_fast==INVALID_HANDLE || m_trend_slow==INVALID_HANDLE) return false;
        }
      return m_fast!=INVALID_HANDLE && m_slow!=INVALID_HANDLE &&
             m_rsi!=INVALID_HANDLE && m_atr!=INVALID_HANDLE;
     }
   void Release(void)
     {
      if(m_fast!=INVALID_HANDLE) IndicatorRelease(m_fast);
      if(m_slow!=INVALID_HANDLE) IndicatorRelease(m_slow);
      if(m_rsi!=INVALID_HANDLE) IndicatorRelease(m_rsi);
      if(m_atr!=INVALID_HANDLE) IndicatorRelease(m_atr);
      if(m_adx!=INVALID_HANDLE) IndicatorRelease(m_adx);
      if(m_trend_fast!=INVALID_HANDLE) IndicatorRelease(m_trend_fast);
      if(m_trend_slow!=INVALID_HANDLE) IndicatorRelease(m_trend_slow);
      m_fast=INVALID_HANDLE; m_slow=INVALID_HANDLE; m_rsi=INVALID_HANDLE; m_atr=INVALID_HANDLE;
      m_adx=INVALID_HANDLE;
      m_trend_fast=INVALID_HANDLE; m_trend_slow=INVALID_HANDLE;
     }
   bool Read(const int minimum_bars,GSMarketSnapshot &snapshot,string &reason)
     {
      ZeroMemory(snapshot);
      if(!SeriesInfoInteger(m_symbol,m_timeframe,SERIES_SYNCHRONIZED) ||
         Bars(m_symbol,m_timeframe)<minimum_bars+1 ||
         BarsCalculated(m_fast)<minimum_bars || BarsCalculated(m_slow)<minimum_bars ||
         BarsCalculated(m_rsi)<minimum_bars || BarsCalculated(m_atr)<minimum_bars ||
         (m_use_adx && BarsCalculated(m_adx)<minimum_bars))
         return GSReject(reason,"HOLD_DATA_INCOMPLETE");
      MqlRates rates[];
      ArraySetAsSeries(rates,true);
      int copied=CopyRates(m_symbol,m_timeframe,1,6,rates);
      if(copied<2)
         return GSReject(reason,"HOLD_CLOSED_BARS_UNAVAILABLE");
      snapshot.bar=rates[0]; snapshot.previous=rates[1];
      long sum_vol=0;
      int count_vol=MathMin(copied,5);
      for(int v=0;v<count_vol;v++) sum_vol+=rates[v].tick_volume;
      snapshot.avg_tick_volume=(count_vol>0 ? (double)sum_vol/count_vol : (double)rates[0].tick_volume);
      snapshot.available_at_server=snapshot.bar.time+PeriodSeconds(m_timeframe);
      if(snapshot.bar.time<=snapshot.previous.time ||
         !GSValidOHLC(snapshot.bar.open,snapshot.bar.high,snapshot.bar.low,snapshot.bar.close) ||
         !GSValidOHLC(snapshot.previous.open,snapshot.previous.high,snapshot.previous.low,snapshot.previous.close))
         return GSReject(reason,"HOLD_INVALID_OHLC");
      if(!ReadValue(m_fast,snapshot.fast_ema) || !ReadValue(m_slow,snapshot.slow_ema) ||
         !ReadPrevious(m_fast,snapshot.previous_fast_ema) || !ReadPrevious(m_slow,snapshot.previous_slow_ema) ||
         !ReadValue(m_rsi,snapshot.rsi) || !ReadValue(m_atr,snapshot.atr) ||
         !GSPositive(snapshot.fast_ema) || !GSPositive(snapshot.slow_ema) ||
         !GSPositive(snapshot.atr) || snapshot.rsi<0.0 || snapshot.rsi>100.0)
         return GSReject(reason,"HOLD_INVALID_INDICATOR");
      if(m_use_adx)
        {
         if(!ReadValue(m_adx,snapshot.adx) || !ReadPrevious(m_adx,snapshot.previous_adx) || !MathIsValidNumber(snapshot.adx) ||
            snapshot.adx<0.0 || snapshot.adx>100.0)
            return GSReject(reason,"HOLD_INVALID_ADX");
        }
      if(m_confirm)
        {
         if(!SeriesInfoInteger(m_symbol,m_trend_timeframe,SERIES_SYNCHRONIZED) ||
            Bars(m_symbol,m_trend_timeframe)<minimum_bars+1 ||
            BarsCalculated(m_trend_fast)<minimum_bars || BarsCalculated(m_trend_slow)<minimum_bars)
            return GSReject(reason,"HOLD_TREND_DATA_INCOMPLETE");
         MqlRates trend[1];
         if(CopyRates(m_symbol,m_trend_timeframe,1,1,trend)!=1 ||
            !ReadValue(m_trend_fast,snapshot.trend_fast_ema) ||
            !ReadPrevious(m_trend_fast,snapshot.previous_trend_fast_ema) ||
            !ReadValue(m_trend_slow,snapshot.trend_slow_ema) ||
            !GSValidOHLC(trend[0].open,trend[0].high,trend[0].low,trend[0].close) ||
            !GSPositive(snapshot.trend_fast_ema) || !GSPositive(snapshot.trend_slow_ema))
            return GSReject(reason,"HOLD_TREND_CLOSED_BAR_UNAVAILABLE");
         snapshot.trend_close=trend[0].close;
         snapshot.trend_available_at_server=trend[0].time+PeriodSeconds(m_trend_timeframe);
         // Do not admit a forming, future or stale H1 bar at a M15 decision time.
         long age=(long)snapshot.available_at_server-(long)snapshot.trend_available_at_server;
         if(age<0 || age>=PeriodSeconds(m_trend_timeframe))
            return GSReject(reason,"HOLD_TREND_BAR_TIME_MISMATCH");
        }
      return true;
     }
  };
#endif
