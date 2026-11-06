#ifndef GOLDSHIELD_SYMBOL_SPEC_MQH
#define GOLDSHIELD_SYMBOL_SPEC_MQH
#include <GoldShield/SafetyMath.mqh>
#include <GoldShield/DomainTypes.mqh>

class GSSymbolSpec
  {
public:
   string symbol;
   double point,tick_size,volume_min,volume_max,volume_step;
   int digits;
   long stops_level,freeze_level;

   bool Load(const string name,string &reason)
     {
      symbol=name;
      if(!SymbolSelect(symbol,true)) return GSReject(reason,"SYMBOL_NOT_AVAILABLE");
      point=SymbolInfoDouble(symbol,SYMBOL_POINT);
      tick_size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      volume_min=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
      volume_max=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
      volume_step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
      digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
      stops_level=SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL);
      freeze_level=SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL);
      if(!GSPositive(point) || !GSPositive(tick_size) || !GSPositive(volume_min) ||
         !GSPositive(volume_step) || !GSPositive(volume_max) || volume_max<volume_min ||
         digits<0 || digits>8 || stops_level<0 || freeze_level<0)
         return GSReject(reason,"INVALID_SYMBOL_METADATA");
      return true;
     }
   bool FreshTick(MqlTick &tick,const int maximum_age,string &reason)
     {
      if(!SymbolInfoTick(symbol,tick) || !GSPositive(tick.bid) ||
         !GSPositive(tick.ask) || tick.ask<tick.bid || tick.time<=0)
         return GSReject(reason,"INVALID_TICK");
      // Both clocks here are broker/server clocks. No UTC assumption.
      datetime now=TimeTradeServer();
      if(now<tick.time-2 || now-tick.time>maximum_age)
         return GSReject(reason,"STALE_TICK_OR_SERVER_CLOCK");
      return true;
     }
   bool Filling(ENUM_ORDER_TYPE_FILLING &policy,string &reason)
     {
      long flags=SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE);
      if((flags & SYMBOL_FILLING_FOK)!=0) { policy=ORDER_FILLING_FOK; return true; }
      if((flags & SYMBOL_FILLING_IOC)!=0) { policy=ORDER_FILLING_IOC; return true; }
      if(SymbolInfoInteger(symbol,SYMBOL_TRADE_EXEMODE)!=SYMBOL_TRADE_EXECUTION_MARKET)
        { policy=ORDER_FILLING_RETURN; return true; }
      return GSReject(reason,"NO_SUPPORTED_FILLING_POLICY");
     }
  };
#endif
