#property copyright "GOLDSHIELD AI EA V2 contributors"
#property version   "1.220"
#property strict
#property description "Phase 1 standalone RULES core. Default SHADOW. Demo only; safety validation pending."

#include <GoldShieldDemo20/SafetyMath.mqh>
#include <GoldShieldDemo20/Settings.mqh>
#include <GoldShieldDemo20/MarketData.mqh>
#include <GoldShieldDemo20/RuleSignal.mqh>
#include <GoldShieldDemo20/TradeReconciler.mqh>
#include <GoldShieldDemo20/OrderExecutor.mqh>
#include <GoldShieldDemo20/ChartUI.mqh>
#include <GoldShieldDemo20/TestReport.mqh>
#include <GoldShieldDemo20/ResearchExport.mqh>

GSSymbolSpec g_symbol;
GSMarketData g_market;
GSStorage g_storage;
GSMetrics g_log;
GSStateMachine g_state;
GSTradeReconciler g_reconciler;
GSRiskFirewall g_risk;
GSOrderExecutor g_executor;
GSOwnedPosition g_owned;
bool g_initialized=false,g_processing=false,g_had_position=false;
bool g_runtime_block=false,g_runtime_hard_block=false;
datetime g_observed_bar=0,g_observed_exit_bar=0;
datetime g_research_first=0;
long g_login=0;
string g_server="",g_signal="HOLD_STARTUP";

void GSProcess(const bool evaluate_signal)
  {
   if(!g_initialized || g_processing) return;
   g_processing=true;
   if(g_login!=AccountInfoInteger(ACCOUNT_LOGIN) || g_server!=AccountInfoString(ACCOUNT_SERVER))
     {
      g_state.Set(ERROR_BLOCKED,"ACCOUNT_CHANGED_REATTACH_REQUIRED",g_log);
      g_processing=false;
      return;
     }
   string reason="";
   if(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      g_state.Set(SAFE_MODE,"DISCONNECTED_SERVER_STOPS_ONLY",g_log);
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false;
      return;
     }
   if(!g_reconciler.Read(TradeSymbol,MagicNumber,g_owned,reason))
     {
      g_runtime_block=true;
      g_storage.Block();
      g_state.Set(ERROR_BLOCKED,reason,g_log);
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false;
      return;
     }
   double pending=g_storage.Get(".pending");
   if(pending>0.0 && pending!=EMPTY_VALUE && g_owned.count>0)
     {
      string expected="GS2|"+IntegerToString((long)pending);
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong t=PositionGetTicket(i);
         if(t==0 || !PositionSelectByTicket(t)) continue;
         if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
           {
            if(PositionGetString(POSITION_COMMENT)==expected)
              {
               if(g_storage.ConfirmEntry(expected))
                  g_log.Event("FILL_CONFIRMED","BROKER_POSITION_PRESENT",StringFormat("ticket=%I64u identifier=%I64d lots=%.8f",
                              t,PositionGetInteger(POSITION_IDENTIFIER),PositionGetDouble(POSITION_VOLUME)));
               break;
              }
           }
        }
     }
   if(g_owned.count==0 && g_owned.pending_orders==0 && g_storage.Get(".pending")<0.0)
     {
      if(!g_storage.FinishClose(TimeTradeServer()+CooldownMinutes*60)) g_storage.Block();
      g_log.Event("EXIT_CONFIRMED","NO_RESIDUAL_EA_POSITION");
     }
   if(g_had_position && g_owned.count==0)
     {
      if(!g_storage.SetCooldown(TimeTradeServer()+CooldownMinutes*60)) g_storage.Block();
      double last_deal_profit=0.0;
      ulong last_pos_id=0;
      bool found_deal=false;
      if(HistorySelect(TimeTradeServer()-86400,TimeTradeServer()+60))
        {
         for(int d=HistoryDealsTotal()-1;d>=0;d--)
           {
            ulong dt=HistoryDealGetTicket(d);
            if(dt>0 && HistoryDealGetString(dt,DEAL_SYMBOL)==TradeSymbol && (ulong)HistoryDealGetInteger(dt,DEAL_MAGIC)==MagicNumber)
              {
               if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(dt,DEAL_ENTRY)==DEAL_ENTRY_OUT)
                 {
                  last_deal_profit=HistoryDealGetDouble(dt,DEAL_PROFIT)+HistoryDealGetDouble(dt,DEAL_SWAP);
                  last_pos_id=(ulong)HistoryDealGetInteger(dt,DEAL_POSITION_ID);
                  found_deal=true;
                  break;
                 }
              }
           }
        }
      if(found_deal)
         g_log.Event("POSITION_CLOSED","BROKER_SNAPSHOT_EMPTY",StringFormat("ticket=%I64u profit=%.2f",last_pos_id,last_deal_profit));
      else
         g_log.Event("POSITION_CLOSED","BROKER_SNAPSHOT_EMPTY","Realized net P/L not calculated in Phase 1");
     }
   g_had_position=(g_owned.count>0);

   // Rule 1: Time-based profit exit (MaxHoldMinutes)
   if(MaxHoldMinutes>0 && g_owned.count>0)
     {
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong t=PositionGetTicket(i);
         if(t==0 || !PositionSelectByTicket(t)) continue;
         if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
           {
            datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
            double profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
            if(TimeTradeServer()-opened>=MaxHoldMinutes*60 && profit>0.0)
              {
               string close_reason="";
               if(g_executor.ClosePosition(t,g_risk,g_log,close_reason,"TIME_EXIT_PROFIT"))
                 {
                  g_log.Event("TIME_PROFIT_EXIT","HOLD_DURATION_TARGET_UNREACHED",
                              StringFormat("ticket=%I64u profit=%.2f hold_sec=%I64d",
                              t,profit,(long)(TimeTradeServer()-opened)));
                 }
              }
           }
        }
     }

   // Rule 2: Break-Even Protection (Kunci Modal) & Dynamic ATR Trailing Stop
   if((UseBreakEvenProtection || UseTrailingStop) && g_owned.count>0)
     {
      GSMarketSnapshot data;
      string m_reason="";
      double live_atr=0.0;
      if(g_market.Read(MinClosedBars,data,m_reason))
         live_atr=data.atr;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong t=PositionGetTicket(i);
         if(t==0 || !PositionSelectByTicket(t)) continue;
         if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
           {
            ENUM_POSITION_TYPE p_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            double open_price=PositionGetDouble(POSITION_PRICE_OPEN);
            double current_sl=PositionGetDouble(POSITION_SL);
            double current_tp=PositionGetDouble(POSITION_TP);
            double current_profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
            MqlTick p_tick;
            if(SymbolInfoTick(TradeSymbol,p_tick))
              {
               double point=SymbolInfoDouble(TradeSymbol,SYMBOL_POINT);
               double spread=SymbolInfoInteger(TradeSymbol,SYMBOL_SPREAD)*point;
               int digits=(int)SymbolInfoInteger(TradeSymbol,SYMBOL_DIGITS);
               if(p_type==POSITION_TYPE_BUY)
                 {
                  // 1. Break-Even Check
                  if(UseBreakEvenProtection && current_sl<open_price)
                    {
                     bool be_trig=(live_atr>0.0) ? (p_tick.bid>=open_price+BreakEvenTriggerATR*live_atr) : (p_tick.bid>=open_price+spread*2.0 && current_profit>0.50);
                     if(be_trig)
                       {
                        double new_sl=NormalizeDouble(open_price+point,digits);
                        string mod_reason="";
                        g_executor.ModifyStops(t,new_sl,current_tp,g_risk,g_log,mod_reason,"BREAK_EVEN");
                        current_sl=new_sl;
                       }
                    }
                  // 2. Trailing Stop Check (aktif setelah SL terkunci di atas modal)
                  if(UseTrailingStop && current_sl>=open_price && live_atr>0.0)
                    {
                     double trail_dist=TrailingStopATR*live_atr;
                     double trail_step=TrailingStepATR*live_atr;
                     double target_sl=NormalizeDouble(p_tick.bid-trail_dist,digits);
                     if(target_sl>=current_sl+trail_step && target_sl>open_price)
                       {
                        string mod_reason="";
                        g_executor.ModifyStops(t,target_sl,current_tp,g_risk,g_log,mod_reason,"TRAILING_STOP");
                       }
                    }
                 }
               else if(p_type==POSITION_TYPE_SELL)
                 {
                  // 1. Break-Even Check
                  if(UseBreakEvenProtection && (current_sl>open_price || current_sl==0.0))
                    {
                     bool be_trig=(live_atr>0.0) ? (p_tick.ask<=open_price-BreakEvenTriggerATR*live_atr) : (p_tick.ask<=open_price-spread*2.0 && current_profit>0.50);
                     if(be_trig)
                       {
                        double new_sl=NormalizeDouble(open_price-point,digits);
                        string mod_reason="";
                        g_executor.ModifyStops(t,new_sl,current_tp,g_risk,g_log,mod_reason,"BREAK_EVEN");
                        current_sl=new_sl;
                       }
                    }
                  // 2. Trailing Stop Check (aktif setelah SL terkunci di bawah modal)
                  if(UseTrailingStop && current_sl<=open_price && current_sl>0.0 && live_atr>0.0)
                    {
                     double trail_dist=TrailingStopATR*live_atr;
                     double trail_step=TrailingStepATR*live_atr;
                     double target_sl=NormalizeDouble(p_tick.ask+trail_dist,digits);
                     if(target_sl<=current_sl-trail_step && target_sl<open_price)
                       {
                        string mod_reason="";
                        g_executor.ModifyStops(t,target_sl,current_tp,g_risk,g_log,mod_reason,"TRAILING_STOP");
                       }
                    }
                 }
              }
           }
        }
     }

   // Rule 3: Early Reversal Exit (Deteksi "bakalan minus" dari closed bar M15)
   datetime current_bar=iTime(TradeSymbol,SignalTimeframe,0);
   if(UseEarlyReversalExit && g_owned.count>0 && current_bar>0 && current_bar!=g_observed_exit_bar)
     {
      g_observed_exit_bar=current_bar;
      GSMarketSnapshot data;
      string m_reason="";
      if(g_market.Read(MinClosedBars,data,m_reason))
        {
         for(int i=PositionsTotal()-1;i>=0;i--)
           {
            ulong t=PositionGetTicket(i);
            if(t==0 || !PositionSelectByTicket(t)) continue;
            if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
              {
               ENUM_POSITION_TYPE p_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
               bool should_exit_early=false;
               string exit_detail="";
               if(p_type==POSITION_TYPE_BUY)
                 {
                  if(data.bar.close<data.fast_ema || data.rsi<45.0)
                    {
                     should_exit_early=true;
                     exit_detail=StringFormat("BUY_REVERSAL close=%.2f ema=%.2f rsi=%.2f",data.bar.close,data.fast_ema,data.rsi);
                    }
                 }
               else if(p_type==POSITION_TYPE_SELL)
                 {
                  if(data.bar.close>data.fast_ema || data.rsi>55.0)
                    {
                     should_exit_early=true;
                     exit_detail=StringFormat("SELL_REVERSAL close=%.2f ema=%.2f rsi=%.2f",data.bar.close,data.fast_ema,data.rsi);
                    }
                 }
               if(should_exit_early)
                 {
                  double cur_profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
                  string c_reason="";
                  if(g_executor.ClosePosition(t,g_risk,g_log,c_reason,"EARLY_REVERSAL_EXIT"))
                    {
                     g_log.Event("EARLY_REVERSAL_EXIT","TREND_INVALIDATED_CUT_LOSS",
                                 StringFormat("ticket=%I64u profit=%.2f detail=%s",t,cur_profit,exit_detail));
                    }
                 }
              }
           }
        }
     }

   // Risk exits precede all signal logic. Never loosen a server stop.
   double reference=g_storage.RiskReference();
   double equity=g_storage.RiskEquity();
   double margin=AccountInfoDouble(ACCOUNT_MARGIN);
   bool equity_alarm=reference==EMPTY_VALUE || !GSPositive(reference) || !GSPositive(equity) ||
                     equity<=reference*EquityShieldMinPctOfReference/100.0;
   bool margin_alarm=margin>0.0 && equity/margin*100.0<MinMarginLevelPct;
   bool position_alarm=g_owned.count>0 &&
                       (!GSPositive(g_owned.sl) || g_owned.floating_pl<=-reference*MaxPositionLossPct/100.0);
   // Latch once. Rewriting it and alternating two reasons on every tick can
   // flood disk/audit output after a stop; risk exits below still run each cycle.
   if((equity_alarm || margin_alarm || position_alarm) &&
      !g_runtime_hard_block && g_storage.Get(".blocked")!=2.0)
     {
      g_runtime_hard_block=true;
      if(!g_storage.Block(true)) g_log.Event("STORAGE_ERROR","RISK_LATCH_WRITE_FAILED");
      reason=(equity_alarm ? "EQUITY_REFERENCE_FLOOR" : (margin_alarm ? "MARGIN_EMERGENCY" : "POSITION_STOP_OR_LOSS_EMERGENCY"));
      g_state.Set(PAUSED_RISK,reason,g_log);
     }
   if(g_runtime_hard_block || g_storage.Get(".blocked")==2.0)
     {
      g_state.Set(PAUSED_RISK,"PERSISTENT_HARD_RISK_LATCH",g_log);
      if(g_owned.count==1)
        {
         if(g_executor.EmergencyClose(g_owned.ticket,g_storage,g_risk,g_log,reason))
            g_state.Set(BASKET_EXITING,reason,g_log);
         else g_state.Set(PAUSED_RISK,reason,g_log);
        }
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false;
      return;
     }
   if(!g_log.Healthy())
     {
      g_runtime_block=true;
      g_storage.Block();
     }
   if(g_runtime_block || g_storage.Get(".blocked")!=0.0 || g_storage.Get(".pending")!=0.0)
     {
      g_state.Set(ERROR_BLOCKED,"PERSISTENT_BLOCK_OR_UNCONFIRMED_ORDER_REVIEW_REQUIRED",g_log);
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false;
      return;
     }
   if(g_owned.count>=MaxAccountPositions || g_owned.pending_orders>0)
     {
      g_state.Set(BASKET_ACTIVE,(g_owned.count>1 ? "MULTI_POSITION_SERVER_SL_TP" : "SINGLE_POSITION_SERVER_SL_TP"),g_log);
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false;
      return;
     }
   if(!GSDemo20CanEnter(g_storage,reason))
     {
      g_state.Set(PAUSED_MANUAL,reason,g_log);
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false; return;
     }
   if(TimeTradeServer()<g_storage.Get(".cooldown"))
     {
      g_state.Set(COOLDOWN,"POST_POSITION_COOLDOWN",g_log);
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false;
      return;
     }
   MqlTick tick;
   if(!g_symbol.FreshTick(tick,StaleTickSeconds,reason))
     {
      g_state.Set(SAFE_MODE,reason,g_log);
      GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
      g_processing=false;
      return;
     }
   g_state.Set(READY,"WAIT_NEXT_CLOSED_BAR",g_log);
   datetime current=iTime(TradeSymbol,SignalTimeframe,0);
   if(evaluate_signal && current>0 && g_observed_bar==0)
      g_observed_bar=current; // History may finish synchronizing after OnInit. Still no attach-time entry.
   else if(evaluate_signal && current>0 && current!=g_observed_bar)
     {
      g_observed_bar=current;
      GSMarketSnapshot data;
      if(!g_market.Read(MinClosedBars,data,reason))
        {
         g_signal=reason;
         g_state.Set(SAFE_MODE,reason,g_log);
        }
      else if(!g_storage.ConsumeBar(data.bar.time))
        {
         g_signal="HOLD_CANDLE_ALREADY_CONSUMED_OR_STORAGE_FAILURE";
         g_state.Set(SAFE_MODE,g_signal,g_log);
        }
      else
        {
         GSAssessCapital(g_symbol,g_storage);
         g_state.Set(SIGNAL_PENDING,"CLOSED_CANDLE_RECEIVED",g_log);
         GSSide side=GSEvaluateRules(data,tick,reason);
         if((tick.ask-tick.bid)/g_symbol.point>MaxAllowedSpreadPoints)
           { side=GS_HOLD; reason="HOLD_SPREAD_LIMIT"; }
         if(UseSpreadATRFilter && GSPositive(data.atr) && (tick.ask-tick.bid)>data.atr*MaxSpreadATRMultiple)
           { side=GS_HOLD; reason="HOLD_SPREAD_ATR_EXCESSIVE"; }
         g_signal=EnumToString(side)+" "+reason;
         g_log.Event("SIGNAL",reason,StringFormat("%s model=%s close=%.5f fast=%.5f slow=%.5f rsi=%.2f atr=%.5f adx=%.2f htf_close=%.5f htf_fast=%.5f htf_slow=%.5f htf_available=%I64d",
                     EnumToString(side),EnumToString(SignalModel),data.bar.close,data.fast_ema,data.slow_ema,
                     data.rsi,data.atr,data.adx,data.trend_close,data.trend_fast_ema,data.trend_slow_ema,
                     (long)data.trend_available_at_server),data.bar.time);
         if(side==GS_HOLD)
            g_state.Set((reason=="HOLD_VOLATILITY_OR_GAP" ? PAUSED_VOLATILITY : READY),reason,g_log);
         else if(ExecutionMode==SHADOW || ExecutionMode==DRY_RUN)
            g_state.Set(READY,"SHADOW_SIGNAL_NO_TRADE_REQUEST",g_log);
         else
           {
            GSTradePlan plan;
            if(!g_risk.BuildPlan(side,data,g_symbol,reference,equity,plan,reason))
               g_state.Set(PAUSED_MANUAL,reason,g_log);
            else
              {
               g_state.Set(OPENING,"RISK_APPROVED_DEMO_ONLY",g_log);
               if(!g_executor.Open(plan,g_storage,g_risk,g_log,reason))
                  g_state.Set(ERROR_BLOCKED,reason,g_log);
              }
           }
        }
     }
   GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
   g_processing=false;
  }

int OnInit(void)
  {
   ZeroMemory(g_owned);
   if(!MQLInfoInteger(MQL_TESTER))
     {
      for(int retry=0;retry<60;retry++)
        {
         if(TerminalInfoInteger(TERMINAL_CONNECTED) && AccountInfoDouble(ACCOUNT_EQUITY)>0.0) break;
         Sleep(250);
        }
      if(!TerminalInfoInteger(TERMINAL_CONNECTED) || AccountInfoDouble(ACCOUNT_EQUITY)<=0.0)
        { Print("DEMO20 account not synchronized; no state or orders created"); return INIT_FAILED; }
     }
   string reason="";
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO || ExecutionMode!=RULES_DEMO ||
      AccountInfoString(ACCOUNT_SERVER)!="Exness-MT5Trial7" || AccountInfoString(ACCOUNT_CURRENCY)!="USD")
     { Print("DEMO20 REFUSES NON-TARGET/REAL ACCOUNT"); return INIT_FAILED; }
   if(!GSValidateSettings(reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_PARAMETERS_INCORRECT; }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     { Print("GOLDSHIELD INIT: HEDGING_ACCOUNT_REQUIRED"); return INIT_FAILED; }
   if(ExecutionMode==RULES_DEMO && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     { Print("GOLDSHIELD INIT: DEMO_ACCOUNT_REQUIRED"); return INIT_FAILED; }
   if(!g_symbol.Load(TradeSymbol,reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_FAILED; }
   if(!g_storage.Init(TradeSymbol,MagicNumber,reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_FAILED; }
   if(!GSConfigureCapital(g_storage,reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_FAILED; }
   if(!GSDemo20Init(g_storage,TradeSymbol,MagicNumber,reason)) { Print("DEMO20 INIT: ",reason); return INIT_FAILED; }
   if(!g_log.Init(g_storage.Key())) { Print("GOLDSHIELD INIT: AUDIT_FILE_UNAVAILABLE"); return INIT_FAILED; }
   g_state.Set(RECOVERY,"RECONCILE_BROKER_BEFORE_SIGNALS",g_log);
   bool need_htf=(SignalModel==GS_TREND_PULLBACK || UseHTFTrendFilter);
   if(!g_market.Init(TradeSymbol,SignalTimeframe,FastEMAPeriod,SlowEMAPeriod,RSIPeriod,ATRPeriod,
                     need_htf,TrendTimeframe,UseADXFilter,ADXPeriod))
     { g_log.Event("INIT_FAILED","INDICATOR_HANDLE_ERROR"); return INIT_FAILED; }
   g_executor.Init();
   g_research_first=TimeCurrent();
   GSAssessCapital(g_symbol,g_storage);
   g_login=AccountInfoInteger(ACCOUNT_LOGIN);
   g_server=AccountInfoString(ACCOUNT_SERVER);
   g_observed_bar=iTime(TradeSymbol,SignalTimeframe,0);
   g_observed_exit_bar=g_observed_bar;
   if(!EventSetTimer(1)) { g_log.Event("INIT_FAILED","TIMER_ERROR"); return INIT_FAILED; }
   g_initialized=true;
   g_log.Event("STARTUP","PHASE1_NOT_RELEASE_APPROVED",EnumToString(ExecutionMode)+" currency="+AccountInfoString(ACCOUNT_CURRENCY));
   GSProcess(false);
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason)
  {
   g_initialized=false;
   EventKillTimer();
   g_market.Release();
   g_log.Event("SHUTDOWN","NO_AUTOMATIC_DEINIT_CLOSE",IntegerToString(reason));
   g_log.Release();
   g_storage.Release();
   if(EnableChartPanel) Comment("");
  }
void OnTick(void) { GSProcess(true); }
void OnTimer(void) { GSProcess(false); }
double OnTester(void)
  {
   GSExportResearchBars(g_research_first,TimeCurrent());
   return GSWriteTesterReport();
  }
void OnTradeTransaction(const MqlTradeTransaction &transaction,
                        const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   if(!g_initialized) return;
   if(transaction.type==TRADE_TRANSACTION_REQUEST && request.symbol==TradeSymbol && request.magic==MagicNumber)
      g_log.Event("TRADE_CALLBACK","SERVER_REQUEST_RESULT",StringFormat("retcode=%u request_id=%u order=%I64u deal=%I64u",
                  result.retcode,result.request_id,result.order,result.deal));
   // Callbacks are audit events, not a fill counter. Reconciliation happens in the next cycle.
  }
