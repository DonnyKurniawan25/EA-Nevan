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
      int basket_cd=(UseFastScalperBasket ? BasketCooldownMinutes : CooldownMinutes);
      if(!g_storage.FinishClose(TimeTradeServer()+basket_cd*60)) g_storage.Block();
      g_log.Event("EXIT_CONFIRMED","NO_RESIDUAL_EA_POSITION");
     }
   if(g_had_position && g_owned.count==0)
     {
      int effective_cooldown=(UseFastScalperBasket ? BasketCooldownMinutes : CooldownMinutes);
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
      if(!UseFastScalperBasket && found_deal && last_deal_profit<0.0 && UseDynamicLossCooldown)
         effective_cooldown=LossCooldownMinutes;
      if(!g_storage.SetCooldown(TimeTradeServer()+effective_cooldown*60)) g_storage.Block();
      if(found_deal)
         g_log.Event("POSITION_CLOSED","BROKER_SNAPSHOT_EMPTY",StringFormat("ticket=%I64u profit=%.2f cooldown=%dm",last_pos_id,last_deal_profit,effective_cooldown));
      else
         g_log.Event("POSITION_CLOSED","BROKER_SNAPSHOT_EMPTY","Realized net P/L not calculated in Phase 1");
     }
   g_had_position=(g_owned.count>0);

   // Rule -3: Operator Reset Latch Command
   if(FileIsExist("GoldShield\\RESET_LATCH"))
     {
      FileDelete("GoldShield\\RESET_LATCH");
      g_runtime_hard_block=false;
      g_runtime_block=false;
      g_storage.Set(".blocked",0.0);
      double cur_eq=AccountInfoDouble(ACCOUNT_EQUITY);
      if(cur_eq>0.0)
        {
         g_storage.Set(".cap_anchor",cur_eq);
         g_storage.Set(".reference",cur_eq);
        }
      g_state.Set(READY,"OPERATOR_MANUAL_RESET_LATCH",g_log);
      g_log.Event("OPERATOR_RESET","LATCH_CLEARED","Equity recovered, latch unblocked by operator");
     }

   // Rule -1: Manual Dashboard Close Command (Interaksi Tombol Tutup Posisi via Web Dashboard)
   if(FileIsExist("GoldShield\\MANUAL_CLOSE"))
     {
      int h=FileOpen("GoldShield\\MANUAL_CLOSE",FILE_READ|FILE_TXT|FILE_ANSI);
      ulong target_ticket=0;
      if(h!=INVALID_HANDLE)
        {
         string line=FileReadString(h);
         target_ticket=(ulong)StringToInteger(line);
         FileClose(h);
        }
      FileDelete("GoldShield\\MANUAL_CLOSE");

      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong t=PositionGetTicket(i);
         if(t==0 || !PositionSelectByTicket(t)) continue;
         ulong pos_magic=(ulong)PositionGetInteger(POSITION_MAGIC);
         if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (pos_magic==MagicNumber || pos_magic==GS_MANUAL_MAGIC))
           {
            if(target_ticket==0 || target_ticket==t)
              {
               string c_reason="";
               double profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
               if(g_executor.ClosePosition(t,g_risk,g_log,c_reason,"MANUAL_DASHBOARD_CLOSE"))
                 {
                  g_log.Event("MANUAL_CLOSE","DASHBOARD_USER_COMMAND",StringFormat("ticket=%I64u profit=%.2f magic=%I64u",t,profit,pos_magic));
                 }
              }
           }
        }
     }

   // Rule -2: Manual Dashboard Open Order Command (Interaksi Pasang Posisi via Web Dashboard)
   if(FileIsExist("GoldShield\\MANUAL_ORDER"))
     {
      int h=FileOpen("GoldShield\\MANUAL_ORDER",FILE_READ|FILE_TXT|FILE_ANSI);
      string order_line="";
      if(h!=INVALID_HANDLE)
        {
         order_line=FileReadString(h);
         FileClose(h);
        }
      FileDelete("GoldShield\\MANUAL_ORDER");

      if(StringLen(order_line)>0)
        {
         // Format: SIDE,LOT,SL,TP
         string parts[];
         int n=StringSplit(order_line,',',parts);
         if(n>=2)
           {
            string ord_side=parts[0];
            double ord_lot=StringToDouble(parts[1]);
            double ord_sl=(n>=3 ? StringToDouble(parts[2]) : 0.0);
            double ord_tp=(n>=4 ? StringToDouble(parts[3]) : 0.0);

            ENUM_ORDER_TYPE req_type=(ord_side=="BUY" ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);

            // Periksa jika SL/TP 0.0, gunakan default ATR pasar terkini
            if(ord_sl<=0.0 || ord_tp<=0.0)
              {
               GSMarketSnapshot m_snap;
               string m_err="";
               double cur_atr=0.0;
               if(g_market.Read(MinClosedBars,m_snap,m_err)) cur_atr=m_snap.atr;
               if(cur_atr<=0.0) cur_atr=10.0;

               MqlTick cur_tick;
               if(SymbolInfoTick(TradeSymbol,cur_tick))
                 {
                  int digits=(int)SymbolInfoInteger(TradeSymbol,SYMBOL_DIGITS);
                  if(ord_side=="BUY")
                    {
                     if(ord_sl<=0.0) ord_sl=NormalizeDouble(cur_tick.ask - StopATRMultiple*cur_atr, digits);
                     if(ord_tp<=0.0) ord_tp=NormalizeDouble(cur_tick.ask + (StopATRMultiple*RewardRiskMultiple)*cur_atr, digits);
                    }
                  else
                    {
                     if(ord_sl<=0.0) ord_sl=NormalizeDouble(cur_tick.bid + StopATRMultiple*cur_atr, digits);
                     if(ord_tp<=0.0) ord_tp=NormalizeDouble(cur_tick.bid - (StopATRMultiple*RewardRiskMultiple)*cur_atr, digits);
                    }
                 }
              }
            string open_reason="";
            g_executor.ManualOpen(TradeSymbol,req_type,ord_lot,ord_sl,ord_tp,"GS2|MANUAL_DASHBOARD",g_log,open_reason);
           }
        }
     }

   // Rule -0.5: Fast Scalper Basket Profit & Emergency Cut-Loss Exit ("ketika biru langsung jual")
   if(UseFastScalperBasket && g_owned.count>0)
     {
      double basket_pl=0.0;
      int basket_owned_count=0;
      ulong basket_tickets[];
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong t=PositionGetTicket(i);
         if(t==0 || !PositionSelectByTicket(t)) continue;
         if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
           {
            double p_pl=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
            basket_pl+=p_pl;
            int sz=ArraySize(basket_tickets);
            ArrayResize(basket_tickets,sz+1);
            basket_tickets[sz]=t;
            basket_owned_count++;
           }
        }
      bool take_profit=(basket_pl>=BasketTakeProfitUSC);
      bool cut_loss=(BasketCutLossUSC>0.0 && basket_pl<=-BasketCutLossUSC);
      if(take_profit || cut_loss)
        {
         string b_action=(take_profit ? "BASKET_PROFIT_EXIT" : "BASKET_CUT_LOSS_EXIT");
         string b_sub=(take_profit ? "BASKET_TARGET_PROFIT_REACHED" : "BASKET_EMERGENCY_CUT_LOSS");
         g_log.Event(b_action,b_sub,StringFormat("positions=%d total_pl=%.2f target=%.2f cut_loss=%.2f",
                     basket_owned_count,basket_pl,BasketTakeProfitUSC,BasketCutLossUSC));
         for(int k=0;k<ArraySize(basket_tickets);k++)
           {
            ulong bt=basket_tickets[k];
            string c_reason="";
            g_executor.ClosePosition(bt,g_risk,g_log,c_reason,b_action);
           }
         g_state.Set(BASKET_EXITING,(take_profit ? "BASKET_PROFIT_EXIT" : "BASKET_CUT_LOSS_EXIT"),g_log);
         g_processing=false;
         return;
        }
     }

   // Rule 0: Friday Pre-Close Exit (Hindari weekend gap risk pada instrumen non-crypto)
   if(UseFridayCloseGuard && g_owned.count>0)
     {
      MqlDateTime broker_time;
      if(TimeToStruct(TimeTradeServer(),broker_time))
        {
         bool is_crypto=(StringFind(TradeSymbol,"BTC")>=0 || StringFind(TradeSymbol,"ETH")>=0 || StringFind(TradeSymbol,"SOL")>=0);
         if(!is_crypto && broker_time.day_of_week==5)
           {
            if(broker_time.hour>FridayCloseHourServer || (broker_time.hour==FridayCloseHourServer && broker_time.min>=FridayCloseMinuteServer))
              {
               for(int i=PositionsTotal()-1;i>=0;i--)
                 {
                  ulong t=PositionGetTicket(i);
                  if(t==0 || !PositionSelectByTicket(t)) continue;
                  if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
                    {
                     string c_reason="";
                     if(g_executor.ClosePosition(t,g_risk,g_log,c_reason,"FRIDAY_PRE_CLOSE_EXIT"))
                       {
                        g_log.Event("FRIDAY_PRE_CLOSE","WEEKEND_GAP_PREVENTION",StringFormat("ticket=%I64u",t));
                       }
                    }
                 }
              }
           }
        }
     }

   // Rule 0.5: Midnight Rollover Profit Lock & Swap Avoidance (Non-Crypto)
   if(UseMidnightProfitClose && g_owned.count>0)
     {
      MqlDateTime broker_time;
      if(TimeToStruct(TimeTradeServer(),broker_time))
        {
         bool is_crypto=(StringFind(TradeSymbol,"BTC")>=0 || StringFind(TradeSymbol,"ETH")>=0 || StringFind(TradeSymbol,"SOL")>=0);
         if(!is_crypto && broker_time.hour==23 && broker_time.min>=MidnightCloseMinuteServer)
           {
            for(int i=PositionsTotal()-1;i>=0;i--)
              {
               ulong t=PositionGetTicket(i);
               if(t==0 || !PositionSelectByTicket(t)) continue;
               if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
                 {
                  double profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
                  if(profit>0.0)
                    {
                     string c_reason="";
                     if(g_executor.ClosePosition(t,g_risk,g_log,c_reason,"MIDNIGHT_PROFIT_CLOSE"))
                       {
                        g_log.Event("MIDNIGHT_ROLLOVER_EXIT","SWAP_AND_SPREAD_PREVENTION",StringFormat("ticket=%I64u profit=%.2f",t,profit));
                       }
                    }
                 }
              }
           }
        }
     }

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

   // Rule 2: Partial Take Profit, Break-Even Protection & Dynamic ATR Trailing Stop
   if((UseBreakEvenProtection || UseTrailingStop || UsePartialTakeProfit) && g_owned.count>0)
     {
      GSMarketSnapshot data;
      string m_reason="";
      double live_atr=0.0;
      double live_adx=0.0;
      if(g_market.Read(MinClosedBars,data,m_reason))
        {
         live_atr=data.atr;
         live_adx=data.adx;
        }
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

               // 0. Partial Take Profit Check (TP 1 di +1.0 ATR)
               if(UsePartialTakeProfit && live_atr>0.0)
                 {
                  string partial_key=StringFormat(".partial_%I64u",t);
                  if(g_storage.Get(partial_key)==0.0)
                    {
                     double gain=(p_type==POSITION_TYPE_BUY ? p_tick.bid-open_price : open_price-p_tick.ask);
                     if(gain>=PartialCloseTriggerATR*live_atr)
                       {
                        double cur_vol=PositionGetDouble(POSITION_VOLUME);
                        GSSymbolSpec spec;
                        string spec_err="";
                        if(spec.Load(TradeSymbol,spec_err))
                          {
                           double step=spec.volume_step;
                           double min_v=spec.volume_min;
                           double target_close=MathFloor((cur_vol*(PartialClosePct/100.0))/step)*step;
                           if(target_close>=min_v && cur_vol-target_close>=min_v)
                             {
                              string p_reason="";
                              if(g_executor.ClosePartial(t,target_close,g_risk,g_log,p_reason))
                                {
                                 g_storage.Set(partial_key,1.0);
                                 double lock_p=(BreakEvenLockATR>0.0 && live_atr>0.0) ? (BreakEvenLockATR*live_atr) : point;
                                 double be_sl=NormalizeDouble(open_price+(p_type==POSITION_TYPE_BUY ? lock_p : -lock_p),digits);
                                 string be_reason="";
                                 g_executor.ModifyStops(t,be_sl,current_tp,g_risk,g_log,be_reason,"PARTIAL_TP_BREAK_EVEN");
                                 current_sl=be_sl;
                                 }
                                 }
                                 else
                                 {
                                 g_storage.Set(partial_key,1.0);
                                 double lock_p=(BreakEvenLockATR>0.0 && live_atr>0.0) ? (BreakEvenLockATR*live_atr) : point;
                                 double be_sl=NormalizeDouble(open_price+(p_type==POSITION_TYPE_BUY ? lock_p : -lock_p),digits);
                                 if((p_type==POSITION_TYPE_BUY && current_sl<be_sl) || (p_type==POSITION_TYPE_SELL && (current_sl>be_sl || current_sl==0.0)))
                                 {
                                 string be_reason="";
                                 g_executor.ModifyStops(t,be_sl,current_tp,g_risk,g_log,be_reason,"TP1_LOCK_BREAK_EVEN");
                                 current_sl=be_sl;
                                 }
                                 }
                          }
                       }
                    }
                 }
               double min_dist=(double)MathMax(g_symbol.stops_level,g_symbol.freeze_level)*point+g_symbol.tick_size;
               string partial_key=StringFormat("tp1_closed_%I64u",t);
               bool has_partial=(g_storage.Get(partial_key)>0.5);
               bool spread_frozen=(SpreadFreezeOnTrailing && live_atr>0.0 && (p_tick.ask-p_tick.bid)>MaxSpreadATRMultiple*live_atr);

               if(p_type==POSITION_TYPE_BUY)
                 {
                  // 1. Break-Even Check
                  if(!spread_frozen && UseBreakEvenProtection && current_sl<open_price)
                    {
                     bool be_trig=(live_atr>0.0) ? (p_tick.bid>=open_price+BreakEvenTriggerATR*live_atr) : (p_tick.bid>=open_price+spread*2.0 && current_profit>0.50);
                     if(be_trig)
                       {
                        double lock_p=(BreakEvenLockATR>0.0 && live_atr>0.0) ? (BreakEvenLockATR*live_atr) : point;
                        double new_sl=NormalizeDouble(open_price+lock_p,digits);
                        if(p_tick.bid-new_sl>=min_dist)
                          {
                           string mod_reason="";
                           g_executor.ModifyStops(t,new_sl,current_tp,g_risk,g_log,mod_reason,"BREAK_EVEN");
                           current_sl=new_sl;
                          }
                       }
                    }
                  // 2. Stepped Profit Lock (Fast Multi-Tier: 0.35 ATR, 0.6 ATR, 1.5 ATR, 2.0 ATR, 3.0 ATR)
                  if(!spread_frozen && UseSteppedProfitLock && live_atr>0.0)
                    {
                     double gain=p_tick.bid-open_price;
                     double gain_atr=gain/live_atr;
                     double locked_profit=0.0;
                     if(UseAcceleratorTrailing)
                       {
                        if(gain_atr>=3.0) locked_profit=2.5*live_atr;
                        else if(gain_atr>=2.0) locked_profit=1.5*live_atr;
                        else if(gain_atr>=1.5) locked_profit=1.0*live_atr;
                        else if(gain_atr>=0.6) locked_profit=0.35*live_atr;
                        else if(gain_atr>=0.35) locked_profit=0.05*live_atr;
                       }
                     else
                       {
                        if(gain_atr>=3.0) locked_profit=2.0*live_atr;
                        else if(gain_atr>=2.0) locked_profit=1.0*live_atr;
                        else if(gain_atr>=1.5) locked_profit=0.5*live_atr;
                        else if(gain_atr>=0.6) locked_profit=0.25*live_atr;
                        else if(gain_atr>=0.35) locked_profit=0.05*live_atr;
                       }
                     if(locked_profit>0.0)
                       {
                        double step_sl=NormalizeDouble(open_price+locked_profit,digits);
                        if(step_sl>current_sl && p_tick.bid-step_sl>=min_dist)
                          {
                           string step_reason="";
                           g_executor.ModifyStops(t,step_sl,current_tp,g_risk,g_log,step_reason,"STEPPED_PROFIT_LOCK");
                           current_sl=step_sl;
                          }
                       }
                    }
                  // 3. Trailing Stop Check (aktif setelah SL terkunci di atas modal)
                  if(!spread_frozen && UseTrailingStop && current_sl>=open_price && live_atr>0.0)
                    {
                     double trail_dist=(has_partial && UseAggressiveRunnerTrailing) ? (PartialTrailingATR*live_atr) : (TrailingStopATR*live_atr);
                     if(UseAdaptiveADXTrailing && live_adx>0.0 && live_adx<25.0)
                        trail_dist=MathMin(trail_dist,AdaptiveLowADXTrailingATR*live_atr);
                     double trail_step=TrailingStepATR*live_atr;
                     double target_sl=NormalizeDouble(p_tick.bid-trail_dist,digits);
                     if(target_sl>p_tick.bid-min_dist)
                        target_sl=NormalizeDouble(p_tick.bid-min_dist,digits);
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
                  if(!spread_frozen && UseBreakEvenProtection && (current_sl>open_price || current_sl==0.0))
                    {
                     bool be_trig=(live_atr>0.0) ? (p_tick.ask<=open_price-BreakEvenTriggerATR*live_atr) : (p_tick.ask<=open_price-spread*2.0 && current_profit>0.50);
                     if(be_trig)
                       {
                        double lock_p=(BreakEvenLockATR>0.0 && live_atr>0.0) ? (BreakEvenLockATR*live_atr) : point;
                        double new_sl=NormalizeDouble(open_price-lock_p,digits);
                        if(new_sl-p_tick.ask>=min_dist)
                          {
                           string mod_reason="";
                           g_executor.ModifyStops(t,new_sl,current_tp,g_risk,g_log,mod_reason,"BREAK_EVEN");
                           current_sl=new_sl;
                          }
                       }
                    }
                  // 2. Stepped Profit Lock (Fast Multi-Tier: 0.35 ATR, 0.6 ATR, 1.5 ATR, 2.0 ATR, 3.0 ATR)
                  if(!spread_frozen && UseSteppedProfitLock && live_atr>0.0)
                    {
                     double gain=open_price-p_tick.ask;
                     double gain_atr=gain/live_atr;
                     double locked_profit=0.0;
                     if(UseAcceleratorTrailing)
                       {
                        if(gain_atr>=3.0) locked_profit=2.5*live_atr;
                        else if(gain_atr>=2.0) locked_profit=1.5*live_atr;
                        else if(gain_atr>=1.5) locked_profit=1.0*live_atr;
                        else if(gain_atr>=0.6) locked_profit=0.35*live_atr;
                        else if(gain_atr>=0.35) locked_profit=0.05*live_atr;
                       }
                     else
                       {
                        if(gain_atr>=3.0) locked_profit=2.0*live_atr;
                        else if(gain_atr>=2.0) locked_profit=1.0*live_atr;
                        else if(gain_atr>=1.5) locked_profit=0.5*live_atr;
                        else if(gain_atr>=0.6) locked_profit=0.25*live_atr;
                        else if(gain_atr>=0.35) locked_profit=0.05*live_atr;
                       }
                     if(locked_profit>0.0)
                       {
                        double step_sl=NormalizeDouble(open_price-locked_profit,digits);
                        if((step_sl<current_sl || current_sl==0.0) && step_sl-p_tick.ask>=min_dist)
                          {
                           string step_reason="";
                           g_executor.ModifyStops(t,step_sl,current_tp,g_risk,g_log,step_reason,"STEPPED_PROFIT_LOCK");
                           current_sl=step_sl;
                          }
                       }
                    }
                  // 3. Trailing Stop Check (aktif setelah SL terkunci di bawah modal)
                  if(!spread_frozen && UseTrailingStop && current_sl<=open_price && current_sl>0.0 && live_atr>0.0)
                    {
                     double trail_dist=(has_partial && UseAggressiveRunnerTrailing) ? (PartialTrailingATR*live_atr) : (TrailingStopATR*live_atr);
                     if(UseAdaptiveADXTrailing && live_adx>0.0 && live_adx<25.0)
                        trail_dist=MathMin(trail_dist,AdaptiveLowADXTrailingATR*live_atr);
                     double trail_step=TrailingStepATR*live_atr;
                     double target_sl=NormalizeDouble(p_tick.ask+trail_dist,digits);
                     if(target_sl<p_tick.ask+min_dist)
                        target_sl=NormalizeDouble(p_tick.ask+min_dist,digits);
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

   // Rule 3: Early Reversal Exit & RSI Overbought/Oversold Profit Protector
   datetime current_bar=iTime(TradeSymbol,SignalTimeframe,0);
   if(g_owned.count>0 && current_bar>0 && current_bar!=g_observed_exit_bar)
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
               double cur_profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
               bool should_exit_early=false;
               string exit_detail="";
               string exit_action="EARLY_REVERSAL_EXIT";
               string exit_sub="TREND_INVALIDATED_CUT_LOSS";

               // 1. RSI Extreme Profit Protector (Amankan profit saat RSI mencapai titik jenuh)
               if(UseRSIProfitProtector && cur_profit>0.0)
                 {
                  if(p_type==POSITION_TYPE_BUY && data.rsi>=RSIExtremeOverbought)
                    {
                     should_exit_early=true;
                     exit_action="RSI_EXTREME_PROFIT_EXIT";
                     exit_sub="RSI_OVERBOUGHT_EXHAUSTION";
                     exit_detail=StringFormat("BUY_RSI_OVERBOUGHT rsi=%.2f limit=%.2f",data.rsi,RSIExtremeOverbought);
                    }
                  else if(p_type==POSITION_TYPE_SELL && data.rsi<=RSIExtremeOversold)
                    {
                     should_exit_early=true;
                     exit_action="RSI_EXTREME_PROFIT_EXIT";
                     exit_sub="RSI_OVERSOLD_EXHAUSTION";
                     exit_detail=StringFormat("SELL_RSI_OVERSOLD rsi=%.2f limit=%.2f",data.rsi,RSIExtremeOversold);
                    }
                 }

               // 2. Early Trend Reversal Cut-Loss
               if(!should_exit_early && UseEarlyReversalExit)
                 {
                  if(p_type==POSITION_TYPE_BUY)
                    {
                     if((data.bar.close<data.fast_ema-data.atr*ReversalBufferATR) ||
                        (data.rsi<50.0-ReversalRSIThreshold))
                       {
                        should_exit_early=true;
                        exit_detail=StringFormat("BUY_REVERSAL close=%.2f ema=%.2f rsi=%.2f buf=%.2f",data.bar.close,data.fast_ema,data.rsi,data.atr*ReversalBufferATR);
                       }
                    }
                  else if(p_type==POSITION_TYPE_SELL)
                    {
                     if((data.bar.close>data.fast_ema+data.atr*ReversalBufferATR) ||
                        (data.rsi>50.0+ReversalRSIThreshold))
                       {
                        should_exit_early=true;
                        exit_detail=StringFormat("SELL_REVERSAL close=%.2f ema=%.2f rsi=%.2f buf=%.2f",data.bar.close,data.fast_ema,data.rsi,data.atr*ReversalBufferATR);
                       }
                    }
                 }

               if(should_exit_early)
                 {
                  string c_reason="";
                  if(g_executor.ClosePosition(t,g_risk,g_log,c_reason,exit_action))
                    {
                     g_log.Event(exit_action,exit_sub,
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
   bool is_cent_acct=(AccountInfoString(ACCOUNT_CURRENCY)=="USC");
   double eff_min_margin=(is_cent_acct ? 150.0 : MinMarginLevelPct);
   bool margin_alarm=margin>0.0 && equity/margin*100.0<eff_min_margin;
   bool position_alarm=g_owned.count>0 &&
                       (!GSPositive(g_owned.sl) || (!UseFastScalperBasket && g_owned.floating_pl<=-reference*MaxPositionLossPct/100.0));
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
      if(g_owned.count==0 && !equity_alarm && !margin_alarm && GSPositive(equity) && equity>=reference*EquityShieldMinPctOfReference/100.0)
        {
         g_runtime_hard_block=false;
         g_runtime_block=false;
         g_storage.Set(".blocked",0.0);
         g_storage.Set(".cap_anchor",equity);
         g_storage.Set(".reference",equity);
         g_state.Set(READY,"AUTO_RECOVERED_HEALTHY_FINANCES",g_log);
         g_log.Event("AUTO_RECOVER","FINANCES_HEALTHY",StringFormat("equity=%.2f margin=%.2f reference=%.2f",equity,margin,reference));
        }
      else
        {
         g_state.Set(PAUSED_RISK,"PERSISTENT_HARD_RISK_LATCH",g_log);
         if(g_owned.count>=1)
           {
            for(int i=PositionsTotal()-1;i>=0;i--)
              {
               ulong t=PositionGetTicket(i);
               if(t==0 || !PositionSelectByTicket(t)) continue;
               if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
                 {
                  g_executor.EmergencyClose(t,g_storage,g_risk,g_log,reason);
                 }
              }
            g_state.Set(BASKET_EXITING,reason,g_log);
           }
         GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());
         g_processing=false;
         return;
        }
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
   if(current>0 && g_observed_bar==0)
      g_observed_bar=current; // History may finish synchronizing after OnInit. Still no attach-time entry.
   else if(current>0 && current!=g_observed_bar)
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
         if(side!=GS_HOLD && g_owned.count>0 && RequireSameDirectionMulti)
           {
            if((g_owned.direction==POSITION_TYPE_BUY && side==GS_SELL) ||
               (g_owned.direction==POSITION_TYPE_SELL && side==GS_BUY))
              {
               side=GS_HOLD;
               reason="HOLD_OPPOSITE_DIRECTION_EXISTS";
              }
           }
         if(side!=GS_HOLD && g_owned.count>0 && RequireProfitForAddOn)
           {
            for(int p_idx=PositionsTotal()-1; p_idx>=0; p_idx--)
              {
               ulong pos_t=PositionGetTicket(p_idx);
               if(pos_t==0 || !PositionSelectByTicket(pos_t)) continue;
               if(PositionGetString(POSITION_SYMBOL)==TradeSymbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
                 {
                  double p_profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
                  if(p_profit<=0.0)
                    {
                     side=GS_HOLD;
                     reason="HOLD_ADDON_EXISTING_NOT_PROFITABLE";
                     break;
                    }
                  if(RequireBreakEvenForAddOn)
                    {
                     ENUM_POSITION_TYPE p_dir=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
                     double p_open=PositionGetDouble(POSITION_PRICE_OPEN);
                     double p_sl=PositionGetDouble(POSITION_SL);
                     bool is_be_locked=(p_dir==POSITION_TYPE_BUY) ? (p_sl>=p_open) : (p_sl>0.0 && p_sl<=p_open);
                     if(!is_be_locked)
                       {
                        side=GS_HOLD;
                        reason="HOLD_ADDON_EXISTING_NOT_BREAKEVEN";
                        break;
                       }
                    }
                  if(MinAddOnDistanceATR>0.0 && GSPositive(data.atr))
                    {
                     double p_open=PositionGetDouble(POSITION_PRICE_OPEN);
                     double dist=MathAbs(data.bar.close-p_open);
                     if(dist<MinAddOnDistanceATR*data.atr)
                       {
                        side=GS_HOLD;
                        reason="HOLD_ADDON_TOO_CLOSE";
                        break;
                       }
                    }
                 }
              }
           }
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
   bool is_demo=(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO &&
                 AccountInfoString(ACCOUNT_SERVER)=="Exness-MT5Trial7" &&
                 AccountInfoString(ACCOUNT_CURRENCY)=="USD");
   bool is_cent=(AccountInfoString(ACCOUNT_CURRENCY)=="USC" &&
                 TradeSymbol=="XAUUSDc" &&
                 StringFind(AccountInfoString(ACCOUNT_SERVER),"Exness")>=0);
   if(!is_demo && !is_cent)
     { Print("DEMO20 REFUSES NON-TARGET/REAL ACCOUNT"); return INIT_FAILED; }
   if(!GSValidateSettings(reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_PARAMETERS_INCORRECT; }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     { Print("GOLDSHIELD INIT: HEDGING_ACCOUNT_REQUIRED"); return INIT_FAILED; }
   if(!is_demo && !is_cent && ExecutionMode==RULES_DEMO && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     { Print("GOLDSHIELD INIT: DEMO_ACCOUNT_REQUIRED"); return INIT_FAILED; }
   if(!g_symbol.Load(TradeSymbol,reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_FAILED; }
   if(!g_storage.Init(TradeSymbol,MagicNumber,reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_FAILED; }
   if(!GSConfigureCapital(g_storage,reason)) { Print("GOLDSHIELD INIT: ",reason); return INIT_FAILED; }
   if((is_demo || is_cent) && !GSDemo20Init(g_storage,TradeSymbol,MagicNumber,reason)) { Print("DEMO20 INIT: ",reason); return INIT_FAILED; }
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
