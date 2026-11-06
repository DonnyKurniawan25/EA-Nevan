#ifndef GOLDSHIELD_TEST_REPORT_MQH
#define GOLDSHIELD_TEST_REPORT_MQH
#include <GoldShield/Settings.mqh>

string GSJsonNumber(const double value)
  {
   if(!MathIsValidNumber(value) || MathAbs(value)>1e100) return "null";
   return DoubleToString(value,8);
  }
string GSJsonString(string value)
  {
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r","\\r");
   StringReplace(value,"\n","\\n");
   return "\""+value+"\"";
  }

// Reporting only. No order authority and no effect on the strategy's decisions.
double GSWriteTesterReport(void)
  {
   if(!MQLInfoInteger(MQL_TESTER)) return 0.0;
   FolderCreate("GoldShield");
   string stem="GoldShield\\test_"+IntegerToString((long)MagicNumber)+"_"+IntegerToString((long)TimeCurrent());
   int trades=(int)TesterStatistics(STAT_TRADES);
   int wins=(int)TesterStatistics(STAT_PROFIT_TRADES);
   int losses=(int)TesterStatistics(STAT_LOSS_TRADES);
   double net=TesterStatistics(STAT_PROFIT);
   string win_rate=(trades>0 ? GSJsonNumber(100.0*wins/trades) : "null");
   string json="{\n  \"schema_version\":\"1.0\",\n  \"source\":\"MT5_STRATEGY_TESTER\",\n";
   json+="  \"symbol\":"+GSJsonString(TradeSymbol)+",\n";
   json+="  \"timeframe\":"+GSJsonString(EnumToString(SignalTimeframe))+",\n";
   json+="  \"execution_mode\":"+GSJsonString(EnumToString(ExecutionMode))+",\n";
   json+="  \"signal_model\":"+GSJsonString(EnumToString(SignalModel))+",\n";
   json+="  \"magic\":"+IntegerToString((long)MagicNumber)+",\n";
   json+="  \"capital_limit_usd\":"+GSJsonNumber(CapitalLimitUSD)+",\n";
   json+="  \"max_daily_loss_pct\":"+GSJsonNumber(MaxDailyLossPct)+",\n";
   json+="  \"max_weekly_loss_pct\":"+GSJsonNumber(MaxWeeklyLossPct)+",\n";
   json+="  \"max_consecutive_daily_losses\":"+IntegerToString(MaxConsecutiveLossesPerDay)+",\n";
   json+="  \"max_entries_per_day\":"+IntegerToString(MaxEntriesPerDay)+",\n";
   json+="  \"currency\":"+GSJsonString(AccountInfoString(ACCOUNT_CURRENCY))+",\n";
   json+="  \"server_end_time\":"+GSJsonString(TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS))+",\n";
   json+="  \"trades\":"+IntegerToString(trades)+",\n  \"wins\":"+IntegerToString(wins)+",\n  \"losses\":"+IntegerToString(losses)+",\n";
   json+="  \"win_rate_pct\":"+win_rate+",\n  \"net_profit\":"+GSJsonNumber(net)+",\n";
   json+="  \"gross_profit\":"+GSJsonNumber(TesterStatistics(STAT_GROSS_PROFIT))+",\n";
   json+="  \"gross_loss\":"+GSJsonNumber(TesterStatistics(STAT_GROSS_LOSS))+",\n";
   json+="  \"profit_factor\":"+GSJsonNumber(TesterStatistics(STAT_PROFIT_FACTOR))+",\n";
   json+="  \"equity_drawdown_pct\":"+GSJsonNumber(TesterStatistics(STAT_EQUITY_DDREL_PERCENT))+",\n";
   json+="  \"equity_drawdown_money\":"+GSJsonNumber(TesterStatistics(STAT_EQUITY_DD))+",\n";
   json+="  \"initial_deposit\":"+GSJsonNumber(TesterStatistics(STAT_INITIAL_DEPOSIT))+",\n";
   json+="  \"expected_payoff\":"+GSJsonNumber(TesterStatistics(STAT_EXPECTED_PAYOFF))+",\n";
   json+="  \"base_lot_cap\":"+GSJsonNumber(BaseLot)+",\n";
   json+="  \"spread_cap_points\":"+IntegerToString(MaxAllowedSpreadPoints)+",\n";
   json+="  \"equity_floor_pct\":"+GSJsonNumber(EquityShieldMinPctOfReference)+",\n";
   json+="  \"deals_file\":"+GSJsonString(stem+"_deals.csv")+",\n";
   json+="  \"production_approved\":false\n}\n";
   int file=FileOpen(stem+".json",FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(file!=INVALID_HANDLE)
     { FileWriteString(file,json); FileFlush(file); FileClose(file); }
   else Print("GOLDSHIELD_TEST_REPORT_WRITE_FAILED ",GetLastError());
   int deals=FileOpen(stem+"_deals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(deals!=INVALID_HANDLE)
     {
      FileWrite(deals,"position_id","deal_ticket","time_server","entry","type","volume",
                "profit","commission","swap","fee","reason");
      if(HistorySelect(0,TimeCurrent()))
         for(int i=0;i<HistoryDealsTotal();i++)
           {
            ulong ticket=HistoryDealGetTicket(i);
            if(ticket==0 || (ulong)HistoryDealGetInteger(ticket,DEAL_MAGIC)!=MagicNumber ||
               HistoryDealGetString(ticket,DEAL_SYMBOL)!=TradeSymbol) continue;
            long type=HistoryDealGetInteger(ticket,DEAL_TYPE);
            if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
            FileWrite(deals,HistoryDealGetInteger(ticket,DEAL_POSITION_ID),ticket,
                      TimeToString((datetime)HistoryDealGetInteger(ticket,DEAL_TIME),TIME_DATE|TIME_SECONDS),
                      HistoryDealGetInteger(ticket,DEAL_ENTRY),type,
                      HistoryDealGetDouble(ticket,DEAL_VOLUME),HistoryDealGetDouble(ticket,DEAL_PROFIT),
                      HistoryDealGetDouble(ticket,DEAL_COMMISSION),HistoryDealGetDouble(ticket,DEAL_SWAP),
                      HistoryDealGetDouble(ticket,DEAL_FEE),HistoryDealGetInteger(ticket,DEAL_REASON));
           }
      FileFlush(deals); FileClose(deals);
     }
   PrintFormat("GOLDSHIELD_TEST_RESULT trades=%d wins=%d losses=%d net=%.2f dd_pct=%.6f file=%s",
               trades,wins,losses,net,TesterStatistics(STAT_EQUITY_DDREL_PERCENT),stem+".json");
   return net;
  }
#endif
