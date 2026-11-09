#ifndef GOLDSHIELD_ORDER_EXECUTOR_MQH
#define GOLDSHIELD_ORDER_EXECUTOR_MQH
#include <Trade/Trade.mqh>
#include <GoldShieldDemo20/RiskFirewall.mqh>
#include <GoldShieldDemo20/Storage.mqh>
#include <GoldShieldDemo20/Metrics.mqh>
#include <GoldShieldDemo20/DemoTrial.mqh>

class GSOrderExecutor
  {
private:
   CTrade m_trade;
public:
   void Init(void)
     {
      m_trade.SetExpertMagicNumber(MagicNumber);
      m_trade.SetDeviationInPoints((ulong)MaxDeviationPoints);
      m_trade.SetAsyncMode(false);
      m_trade.SetMarginMode();
     }
   bool Open(const GSTradePlan &plan,GSStorage &store,GSRiskFirewall &risk,
             GSMetrics &log,string &reason)
     {
      if(!EnableAutoTrading || !risk.CanManage(reason)) return false;
      if(!GSPositive(plan.sl) || !GSPositive(plan.tp) || !GSPositive(plan.volume))
         return GSReject(reason,"EXECUTOR_REQUIRES_PROTECTIVE_STOPS");
      // Reconcile again immediately before submission; never retry an uncertain entry.
      int count_owned=0;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         if(PositionGetTicket(i)==0) return GSReject(reason,"PRE_SEND_POSITION_READ_FAILED");
         if(PositionGetString(POSITION_SYMBOL)==TradeSymbol &&
            (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
            count_owned++;
        }
      if(count_owned>=MaxAccountPositions)
         return GSReject(reason,"PRE_SEND_BASKET_ALREADY_EXISTS");
      if(OrdersTotal()>0) return GSReject(reason,"PRE_SEND_PENDING_ORDER_EXISTS");
      MqlTradeRequest request={};
      MqlTradeCheckResult check={};
      request.action=TRADE_ACTION_DEAL;
      request.magic=MagicNumber;
      request.symbol=TradeSymbol;
      request.volume=plan.volume;
      request.type=(plan.side==GS_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      request.price=plan.entry;
      request.sl=plan.sl;
      request.tp=plan.tp;
      request.deviation=(ulong)MaxDeviationPoints;
      request.type_filling=plan.filling;
      request.comment=plan.comment;
      ResetLastError();
      if(!OrderCheck(request,check) || !GSPreflightCodeOK(check.retcode))
        {
         log.Event("ORDER_CHECK","BROKER_PREFLIGHT_REJECTED",StringFormat("retcode=%u error=%d",check.retcode,GetLastError()),plan.candle_id);
         return GSReject(reason,"BROKER_PREFLIGHT_REJECTED");
        }
      if(!MathIsValidNumber(check.margin_free) || !MathIsValidNumber(check.equity) ||
         !MathIsValidNumber(check.margin) || check.equity<=0.0 || check.margin<0.0 ||
         check.margin_free<check.equity*MinFreeMarginPct/100.0 ||
         (check.margin>0.0 && check.equity/check.margin*100.0<MinMarginLevelPct))
         return GSReject(reason,"BROKER_PREFLIGHT_MARGIN_LIMIT");
      if(!store.BeginEntry(plan.candle_id)) return GSReject(reason,"DURABLE_ENTRY_INTENT_FAILED");
      log.Event("ORDER_INTENT","BASELINE_RULES",StringFormat("lots=%.8f entry=%.8f sl=%.8f tp=%.8f budget=%.2f risk_est=%.2f margin_est=%.2f",
                plan.volume,plan.entry,plan.sl,plan.tp,plan.risk_budget,plan.estimated_loss,plan.estimated_margin),plan.candle_id);
      if(!log.Healthy()) return GSReject(reason,"ORDER_INTENT_AUDIT_WRITE_FAILED");
      m_trade.SetTypeFilling(plan.filling);
      if(!GSDemo20Reserve(store,reason)) return false;
      bool sent=m_trade.PositionOpen(TradeSymbol,request.type,plan.volume,plan.entry,plan.sl,plan.tp,plan.comment);
      uint code=m_trade.ResultRetcode();
      log.Event("ORDER_RESULT","RECONCILIATION_REQUIRED",StringFormat("method=%s retcode=%u order=%I64u deal=%I64u filled_volume=%.8f filled_price=%.8f",
                (sent ? "true" : "false"),code,m_trade.ResultOrder(),m_trade.ResultDeal(),m_trade.ResultVolume(),m_trade.ResultPrice()),plan.candle_id);
      // A true return, DONE or DONE_PARTIAL is not a position snapshot confirmation.
      reason="ENTRY_INTENT_AWAITING_BROKER_SNAPSHOT";
      return true;
     }
   bool EmergencyClose(const ulong ticket,GSStorage &store,GSRiskFirewall &risk,
                       GSMetrics &log,string &reason)
     {
      if(!risk.CanManage(reason)) return false;
      if(!PositionSelectByTicket(ticket)) return GSReject(reason,"CLOSE_TICKET_NO_LONGER_PRESENT");
      if(PositionGetString(POSITION_SYMBOL)!=TradeSymbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber ||
         StringFind(PositionGetString(POSITION_COMMENT),"GS2|")!=0)
         return GSReject(reason,"CLOSE_OWNERSHIP_REJECTED");
      if(store.Get(".close_tries")>=3.0) return GSReject(reason,"CLOSE_RETRY_LIMIT_OPERATOR_REQUIRED");
      if(TimeTradeServer()-store.Get(".close_time")<10)
         return GSReject(reason,"CLOSE_RETRY_BACKOFF");
      GSSymbolSpec spec;
      if(!spec.Load(TradeSymbol,reason)) return false;
      ENUM_ORDER_TYPE_FILLING filling;
      if(!spec.Filling(filling,reason)) return false;
      if(!store.BeginClose() || !store.RecordCloseAttempt())
         return GSReject(reason,"DURABLE_CLOSE_INTENT_FAILED");
      m_trade.SetTypeFilling(filling);
      bool sent=m_trade.PositionClose(ticket,(ulong)MaxDeviationPoints);
      log.Event("CLOSE_RESULT","VERIFY_RESIDUAL_POSITION",StringFormat("ticket=%I64u method=%s retcode=%u deal=%I64u",
                ticket,(sent ? "true" : "false"),m_trade.ResultRetcode(),m_trade.ResultDeal()));
      reason="CLOSE_REQUEST_SENT_RECONCILE";
      return true;
     }
   bool ClosePosition(const ulong ticket,GSRiskFirewall &risk,GSMetrics &log,string &reason,string exit_event="TIME_EXIT_PROFIT")
     {
      if(!risk.CanManage(reason)) return false;
      if(!PositionSelectByTicket(ticket)) return GSReject(reason,"CLOSE_TICKET_NO_LONGER_PRESENT");
      if(PositionGetString(POSITION_SYMBOL)!=TradeSymbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber ||
         StringFind(PositionGetString(POSITION_COMMENT),"GS2|")!=0)
         return GSReject(reason,"CLOSE_OWNERSHIP_REJECTED");
      double cur_profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
      GSSymbolSpec spec;
      if(!spec.Load(TradeSymbol,reason)) return false;
      ENUM_ORDER_TYPE_FILLING filling;
      if(!spec.Filling(filling,reason)) return false;
      m_trade.SetTypeFilling(filling);
      bool sent=m_trade.PositionClose(ticket,(ulong)MaxDeviationPoints);
      log.Event("CLOSE_RESULT",exit_event,StringFormat("ticket=%I64u method=%s retcode=%u deal=%I64u profit=%.2f",
                ticket,(sent ? "true" : "false"),m_trade.ResultRetcode(),m_trade.ResultDeal(),cur_profit));
      reason="CLOSE_REQUEST_SENT_RECONCILE";
      return sent;
     }
   bool ClosePartial(const ulong ticket,const double volume,GSRiskFirewall &risk,GSMetrics &log,string &reason)
     {
      if(!risk.CanManage(reason)) return false;
      if(!PositionSelectByTicket(ticket)) return GSReject(reason,"CLOSE_TICKET_NO_LONGER_PRESENT");
      if(PositionGetString(POSITION_SYMBOL)!=TradeSymbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber ||
         StringFind(PositionGetString(POSITION_COMMENT),"GS2|")!=0)
         return GSReject(reason,"CLOSE_OWNERSHIP_REJECTED");
      double cur_profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
      GSSymbolSpec spec;
      if(!spec.Load(TradeSymbol,reason)) return false;
      ENUM_ORDER_TYPE_FILLING filling;
      if(!spec.Filling(filling,reason)) return false;
      m_trade.SetTypeFilling(filling);
      bool sent=m_trade.PositionClosePartial(ticket,volume,(ulong)MaxDeviationPoints);
      log.Event("PARTIAL_CLOSE","TAKE_PROFIT_1",StringFormat("ticket=%I64u close_vol=%.2f method=%s retcode=%u deal=%I64u profit=%.2f",
                ticket,volume,(sent ? "true" : "false"),m_trade.ResultRetcode(),m_trade.ResultDeal(),cur_profit));
      reason="PARTIAL_CLOSE_SENT";
      return sent;
     }
   bool ManualOpen(const string symbol,const ENUM_ORDER_TYPE ord_type,const double volume,
                   const double sl,const double tp,const string comment,
                   GSMetrics &log,string &reason)
     {
      GSSymbolSpec spec;
      if(!spec.Load(symbol,reason)) return false;
      ENUM_ORDER_TYPE_FILLING filling;
      if(!spec.Filling(filling,reason)) return false;
      m_trade.SetTypeFilling(filling);
      MqlTick tick;
      if(!SymbolInfoTick(symbol,tick)) return GSReject(reason,"TICK_READ_FAILED");
      double price=(ord_type==ORDER_TYPE_BUY ? tick.ask : tick.bid);
      bool sent=m_trade.PositionOpen(symbol,ord_type,volume,price,sl,tp,comment);
      uint code=m_trade.ResultRetcode();
      log.Event("MANUAL_ORDER","DASHBOARD_COMMAND",
                StringFormat("type=%s lots=%.2f price=%.2f sl=%.2f tp=%.2f retcode=%u deal=%I64u order=%I64u",
                (ord_type==ORDER_TYPE_BUY ? "BUY" : "SELL"),volume,price,sl,tp,code,m_trade.ResultDeal(),m_trade.ResultOrder()));
      reason=(sent ? "MANUAL_ORDER_SUCCESS" : "MANUAL_ORDER_FAILED");
      return sent;
     }
   bool ModifyStops(const ulong ticket,const double sl,const double tp,GSRiskFirewall &risk,GSMetrics &log,string &reason,const string modify_reason="BREAK_EVEN")
     {
      if(!risk.CanManage(reason)) return false;
      if(!PositionSelectByTicket(ticket)) return GSReject(reason,"MODIFY_TICKET_NO_LONGER_PRESENT");
      if(PositionGetString(POSITION_SYMBOL)!=TradeSymbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber ||
         StringFind(PositionGetString(POSITION_COMMENT),"GS2|")!=0)
         return GSReject(reason,"MODIFY_OWNERSHIP_REJECTED");
      bool sent=false;
      for(int attempt=1;attempt<=3;attempt++)
        {
         sent=m_trade.PositionModify(ticket,sl,tp);
         uint code=m_trade.ResultRetcode();
         if(sent || code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_NO_CHANGES)
           {
            sent=true;
            break;
           }
         Sleep(500); // Re-try jeda 500ms jika requote / harga bergerak cepat
        }
      log.Event("STOP_MODIFY",modify_reason,StringFormat("ticket=%I64u sent=%s retcode=%u sl=%.5f tp=%.5f",
                ticket,(sent ? "true" : "false"),m_trade.ResultRetcode(),sl,tp));
      return sent;
     }
  };
#endif
