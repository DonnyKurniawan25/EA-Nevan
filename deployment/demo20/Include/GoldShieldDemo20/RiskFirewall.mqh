#ifndef GOLDSHIELD_RISK_FIREWALL_MQH
#define GOLDSHIELD_RISK_FIREWALL_MQH
#include <GoldShieldDemo20/Settings.mqh>
#include <GoldShieldDemo20/SymbolSpec.mqh>
#include <GoldShieldDemo20/LossLimits.mqh>

class GSRiskFirewall
  {
private:
   bool AccountExposure(double &risk,double &lots,string &reason)
     {
      risk=0.0; lots=0.0;
      if(OrdersTotal()>0) return GSReject(reason,"ACCOUNT_PENDING_ORDERS_BLOCK_ENTRY");
      if(PositionsTotal()>=MaxAccountPositions)
         return GSReject(reason,"ACCOUNT_POSITION_LIMIT");
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0 || !PositionSelectByTicket(ticket))
            return GSReject(reason,"ACCOUNT_EXPOSURE_UNAVAILABLE");
         string symbol=PositionGetString(POSITION_SYMBOL);
         double volume=PositionGetDouble(POSITION_VOLUME);
         double stop=PositionGetDouble(POSITION_SL);
         if(!GSPositive(stop) || !GSPositive(volume))
            return GSReject(reason,"ACCOUNT_POSITION_WITHOUT_KNOWN_STOP");
         MqlTick tick;
         if(!SymbolInfoTick(symbol,tick) || !GSPositive(tick.bid) || !GSPositive(tick.ask) ||
            TimeTradeServer()-tick.time>StaleTickSeconds)
            return GSReject(reason,"ACCOUNT_EXPOSURE_QUOTE_UNAVAILABLE");
         ENUM_ORDER_TYPE type=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
         double current=(type==ORDER_TYPE_BUY ? tick.bid : tick.ask);
         if((type==ORDER_TYPE_BUY && stop>=current) || (type==ORDER_TYPE_SELL && stop<=current))
            return GSReject(reason,"ACCOUNT_STOP_ALREADY_CROSSED");
         double profit=0.0;
         if(!OrderCalcProfit(type,symbol,volume,current,stop,profit) || !MathIsValidNumber(profit))
            return GSReject(reason,"ACCOUNT_RISK_CALCULATION_FAILED");
         risk+=MathMax(0.0,-profit)*(1.0+RiskBufferPct/100.0)+CostBufferPerLot*volume;
         lots+=volume;
        }
      return true;
     }
   bool BrokerSessionOpen(const string symbol,string &reason)
     {
      MqlDateTime now;
      TimeToStruct(TimeTradeServer(),now);
      int seconds=now.hour*3600+now.min*60+now.sec;
      if(UseSessionFilter && (now.hour<SessionStartHourServer || now.hour>=SessionEndHourServer))
         return GSReject(reason,"HOLD_SESSION_FILTER_CLOSED");
      if(BlockMidnightRollover)
        {
         if((now.hour==23 && now.min>=RolloverStartMinute) ||
            (now.hour==0 && now.min<RolloverEndMinute))
            return GSReject(reason,"HOLD_MIDNIGHT_ROLLOVER");
        }
      if(UseWeeklyOpenGuard)
        {
         bool is_crypto=(StringFind(symbol,"BTC")>=0 || StringFind(symbol,"ETH")>=0 || StringFind(symbol,"SOL")>=0);
         if(!is_crypto)
           {
            if((now.day_of_week==1 && now.hour==0 && now.min<WeeklyOpenWaitMinutes) ||
               (now.day_of_week==0 && now.hour>=22))
               return GSReject(reason,"HOLD_WEEKLY_OPEN_STABILIZATION");
           }
        }
      if(UseFridayCloseGuard)
        {
         bool is_crypto=(StringFind(symbol,"BTC")>=0 || StringFind(symbol,"ETH")>=0 || StringFind(symbol,"SOL")>=0);
         if(!is_crypto && now.day_of_week==5)
           {
            if(now.hour>FridayCloseHourServer || (now.hour==FridayCloseHourServer && now.min>=FridayCloseMinuteServer))
               return GSReject(reason,"HOLD_FRIDAY_WEEKEND_APPROACHING");
           }
        }
      for(uint index=0;index<32;index++)
        {
         datetime from=0,to=0;
         if(!SymbolInfoSessionTrade(symbol,(ENUM_DAY_OF_WEEK)now.day_of_week,index,from,to)) break;
         long start=(long)from%86400,finish=(long)to%86400;
         if((long)to-(long)from>=86400 || start==finish) return true;
         if(start<finish && seconds>=start && seconds<finish) return true;
         if(start>finish && (seconds>=start || seconds<finish)) return true;
        }
      return GSReject(reason,"HOLD_MARKET_SESSION_CLOSED");
     }
public:
   bool CanManage(string &reason)
     {
      if(ExecutionMode!=RULES_DEMO || !DemoTradingOptIn)
         return GSReject(reason,"MONITOR_ONLY_NO_TRADE_REQUESTS");
      // Real execution is deliberately unavailable, including when an input is changed.
      if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
         return GSReject(reason,"DEMO_ACCOUNT_REQUIRED");
      if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
         return GSReject(reason,"HEDGING_ACCOUNT_REQUIRED");
      if(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))
         return GSReject(reason,"TERMINAL_DISCONNECTED");
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
         !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
         return GSReject(reason,"ALGORITHMIC_TRADING_NOT_ALLOWED");
      return true;
     }
   bool BuildPlan(const GSSide side,const GSMarketSnapshot &data,GSSymbolSpec &spec,const double reference,const double risk_equity,
                  GSTradePlan &plan,string &reason)
     {
      ZeroMemory(plan);
      if(side!=GS_BUY && side!=GS_SELL) return GSReject(reason,"HOLD_NO_DIRECTION");
      if(!EnableAutoTrading) return GSReject(reason,"AUTO_ENTRY_DISABLED");
      if(!CanManage(reason)) return false;
      if(!spec.Load(TradeSymbol,reason)) return false; // Reload current broker constraints.
      MqlTick tick;
      if(!spec.FreshTick(tick,StaleTickSeconds,reason)) return false;
      if((tick.ask-tick.bid)/spec.point>MaxAllowedSpreadPoints)
         return GSReject(reason,"HOLD_SPREAD_LIMIT");
      if(UseSpreadATRFilter && GSPositive(data.atr) && (tick.ask-tick.bid)>data.atr*MaxSpreadATRMultiple)
         return GSReject(reason,"HOLD_SPREAD_ATR_EXCESSIVE");
      if(!BrokerSessionOpen(spec.symbol,reason)) return false;
      long mode=SymbolInfoInteger(spec.symbol,SYMBOL_TRADE_MODE);
      if(mode==SYMBOL_TRADE_MODE_DISABLED || mode==SYMBOL_TRADE_MODE_CLOSEONLY ||
         (side==GS_BUY && mode==SYMBOL_TRADE_MODE_SHORTONLY) ||
         (side==GS_SELL && mode==SYMBOL_TRADE_MODE_LONGONLY))
         return GSReject(reason,"SYMBOL_DIRECTION_NOT_ALLOWED");
      long order_mode=SymbolInfoInteger(spec.symbol,SYMBOL_ORDER_MODE);
      if((order_mode & SYMBOL_ORDER_MARKET)==0 || (order_mode & SYMBOL_ORDER_SL)==0 ||
         (order_mode & SYMBOL_ORDER_TP)==0)
         return GSReject(reason,"SERVER_MARKET_SL_TP_REQUIRED");
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      double balance=AccountInfoDouble(ACCOUNT_BALANCE);
      double free_margin=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      double used_margin=AccountInfoDouble(ACCOUNT_MARGIN);
      if(!GSPositive(equity) || !GSPositive(balance) || !GSPositive(free_margin) ||
         !MathIsValidNumber(used_margin) || used_margin<0.0)
         return GSReject(reason,"INVALID_ACCOUNT_FINANCES");
      if(used_margin>0.0 && equity/used_margin*100.0<MinMarginLevelPct)
         return GSReject(reason,"CURRENT_MARGIN_LEVEL_LOW");
      double account_risk=0.0,account_lots=0.0;
      if(!AccountExposure(account_risk,account_lots,reason)) return false;
      GSLossBudget limits;
      if(!GSReadLossBudget(reference,risk_equity,limits,reason)) return false;
      double budget_equity=MathMin(equity,risk_equity);
      plan.risk_budget=MathMin(budget_equity*MaxRiskPerTradePct/100.0,
                              budget_equity*MaxAggregateOpenRiskPct/100.0-account_risk);
      plan.risk_budget=MathMin(plan.risk_budget,MathMax(0.0,limits.available-account_risk));
      if(!GSPositive(plan.risk_budget)) return GSReject(reason,"AGGREGATE_RISK_BUDGET_EXHAUSTED");
      double spread_profit=0.0;
      if(!OrderCalcProfit(ORDER_TYPE_BUY,spec.symbol,spec.volume_min,tick.ask,tick.bid,spread_profit) ||
         !MathIsValidNumber(spread_profit) || spread_profit>0.0)
         return GSReject(reason,"MINIMUM_COST_CALCULATION_FAILED");
      double cost_floor=(-spread_profit)*(1.0+RiskBufferPct/100.0)+CostBufferPerLot*spec.volume_min;
      if(cost_floor>plan.risk_budget+1e-8)
         return GSReject(reason,"MINIMUM_LOT_COST_EXCEEDS_CAPITAL_RISK");
      bool buy=(side==GS_BUY);
      plan.side=side;
      plan.candle_id=data.bar.time;
      plan.entry=(buy ? tick.ask : tick.bid);
      double minimum=(double)MathMax(spec.stops_level,spec.freeze_level)*spec.point+spec.tick_size;
      double effective_rr=RewardRiskMultiple;
      if(UseVolatilityExpansionTP && data.adx>=30.0)
         effective_rr=MathMax(RewardRiskMultiple,1.75);
      if(buy)
        {
         double raw=MathMin(plan.entry-data.atr*StopATRMultiple,data.bar.low-spec.tick_size);
         plan.sl=GSTickDown(MathMin(raw,tick.bid-minimum),spec.tick_size,spec.digits);
         plan.tp=GSTickUp(plan.entry+(plan.entry-plan.sl)*effective_rr,spec.tick_size,spec.digits);
        }
      else
        {
         double raw=MathMax(plan.entry+data.atr*StopATRMultiple,data.bar.high+spec.tick_size);
         plan.sl=GSTickUp(MathMax(raw,tick.ask+minimum),spec.tick_size,spec.digits);
         plan.tp=GSTickDown(plan.entry-(plan.sl-plan.entry)*effective_rr,spec.tick_size,spec.digits);
        }
      if(!GSValidStops(buy,plan.entry,tick.bid,tick.ask,plan.sl,plan.tp,minimum))
         return GSReject(reason,"INVALID_SERVER_STOP_OR_TARGET");
      ENUM_ORDER_TYPE type=(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      double reference_profit=0.0;
      if(!OrderCalcProfit(type,spec.symbol,spec.volume_min,plan.entry,plan.sl,reference_profit) ||
         !MathIsValidNumber(reference_profit) || reference_profit>=0.0)
         return GSReject(reason,"STOP_LOSS_CALCULATION_FAILED");
      double loss_per_lot=-reference_profit/spec.volume_min;
      double max_allowed=MaxTotalAccountLots-account_lots;
      double cap=(UseAutoLotByRisk ? (MaxLotPerTrade>0.0 ? MathMin(MaxLotPerTrade,max_allowed) : max_allowed)
                                   : MathMin(BaseLot,max_allowed));
      plan.volume=GSRiskVolume(plan.risk_budget,loss_per_lot,RiskBufferPct,CostBufferPerLot,
                              cap,spec.volume_min,spec.volume_max,spec.volume_step);
      if(plan.volume<=0.0) return GSReject(reason,"MINIMUM_LOT_EXCEEDS_RISK_OR_VOLUME_BUDGET");
      plan.estimated_loss=plan.volume*(loss_per_lot*(1.0+RiskBufferPct/100.0)+CostBufferPerLot);
      if(plan.estimated_loss>plan.risk_budget+1e-8)
         return GSReject(reason,"RISK_ROUNDING_OVER_BUDGET");
      if(!OrderCalcMargin(type,spec.symbol,plan.volume,plan.entry,plan.estimated_margin) ||
         !MathIsValidNumber(plan.estimated_margin) || plan.estimated_margin<0.0)
         return GSReject(reason,"MARGIN_CALCULATION_FAILED");
      double projected=used_margin+plan.estimated_margin;
      if(!GSCapitalMarginOK(budget_equity,used_margin,plan.estimated_margin,MinFreeMarginPct,MinMarginLevelPct))
         return GSReject(reason,"CAPITAL_MARGIN_HEADROOM_TOO_SMALL");
      if(free_margin-plan.estimated_margin<equity*MinFreeMarginPct/100.0 ||
         (projected>0.0 && equity/projected*100.0<MinMarginLevelPct))
         return GSReject(reason,"PROJECTED_MARGIN_HEADROOM_LOW");
      if(!spec.Filling(plan.filling,reason)) return false;
      plan.comment="GS2|"+IntegerToString((long)plan.candle_id);
      return true;
     }
  };
#endif
