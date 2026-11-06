#ifndef GOLDSHIELD_LOSS_LIMITS_MQH
#define GOLDSHIELD_LOSS_LIMITS_MQH
#include <GoldShieldDemo20/Settings.mqh>

struct GSLossBudget
  {
   double daily_net,weekly_net,available;
   int entries_today,loss_streak;
  };
struct GSHistoryPosition
  {
   long id;
   ulong last_ticket;
   double net,volume_in,volume_out;
   datetime first_entry,last_exit;
  };

// Rebuild from broker history at entry preflight: restart cannot erase limits.
// Deposit/credit/withdrawal deals are not trading P/L. Negative ancillary charges
// count conservatively; positive non-trade adjustments never replenish budgets.
bool GSReadLossBudget(const double reference,const double equity,GSLossBudget &budget,string &reason)
  {
   ZeroMemory(budget);
   datetime now=TimeTradeServer();
   MqlDateTime date;
   if(now<=0 || !TimeToStruct(now,date)) return GSReject(reason,"HOLD_HISTORY_CLOCK_UNAVAILABLE");
   date.hour=0; date.min=0; date.sec=0;
   datetime day=StructToTime(date);
   datetime week=day-((date.day_of_week+6)%7)*86400;
   if(!HistorySelect(0,now)) return GSReject(reason,"HOLD_RISK_HISTORY_UNAVAILABLE");
   GSHistoryPosition positions[];
   int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
     {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) return GSReject(reason,"HOLD_RISK_HISTORY_READ_FAILED");
      long type=HistoryDealGetInteger(ticket,DEAL_TYPE);
      datetime when=(datetime)HistoryDealGetInteger(ticket,DEAL_TIME);
      double net=HistoryDealGetDouble(ticket,DEAL_PROFIT)+HistoryDealGetDouble(ticket,DEAL_COMMISSION)+
                 HistoryDealGetDouble(ticket,DEAL_SWAP)+HistoryDealGetDouble(ticket,DEAL_FEE);
      if(!MathIsValidNumber(net)) return GSReject(reason,"HOLD_RISK_HISTORY_NONFINITE");
      bool trade=(type==DEAL_TYPE_BUY || type==DEAL_TYPE_SELL);
      if(!trade && (type==DEAL_TYPE_BALANCE || type==DEAL_TYPE_CREDIT)) continue;
      double account_net=(trade ? net : MathMin(0.0,net));
      if(when>=day) budget.daily_net+=account_net;
      if(when>=week) budget.weekly_net+=account_net;
      if((ulong)HistoryDealGetInteger(ticket,DEAL_MAGIC)!=MagicNumber ||
         HistoryDealGetString(ticket,DEAL_SYMBOL)!=TradeSymbol) continue;
      long id=HistoryDealGetInteger(ticket,DEAL_POSITION_ID);
      if(id<=0) continue;
      int index=-1;
      for(int j=0;j<ArraySize(positions);j++) if(positions[j].id==id) { index=j; break; }
      if(index<0)
        {
         index=ArraySize(positions);
         if(ArrayResize(positions,index+1)!=index+1) return GSReject(reason,"HOLD_RISK_HISTORY_MEMORY");
         ZeroMemory(positions[index]); positions[index].id=id;
        }
      positions[index].net+=net;
      if(!trade) continue;
      long entry=HistoryDealGetInteger(ticket,DEAL_ENTRY);
      double volume=HistoryDealGetDouble(ticket,DEAL_VOLUME);
      if(!GSPositive(volume) || (entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY))
         return GSReject(reason,"HOLD_RISK_HISTORY_ENTRY_UNSUPPORTED");
      if(entry==DEAL_ENTRY_IN)
        {
         positions[index].volume_in+=volume;
         if(positions[index].first_entry==0 || when<positions[index].first_entry)
            positions[index].first_entry=when;
        }
      else
        {
         positions[index].volume_out+=volume;
         if(when>positions[index].last_exit ||
            (when==positions[index].last_exit && ticket>positions[index].last_ticket))
           { positions[index].last_exit=when; positions[index].last_ticket=ticket; }
        }
     }
   GSHistoryPosition closed[];
   for(int i=0;i<ArraySize(positions);i++)
     {
      if(positions[i].first_entry>=day) budget.entries_today++;
      if(positions[i].last_exit<day || positions[i].volume_in<=0.0 ||
         MathAbs(positions[i].volume_in-positions[i].volume_out)>1e-8) continue;
      int size=ArraySize(closed);
      if(ArrayResize(closed,size+1)!=size+1) return GSReject(reason,"HOLD_RISK_HISTORY_MEMORY");
      closed[size]=positions[i];
     }
   // Explicit chronological order, including multiple exits in the same second.
   for(int i=1;i<ArraySize(closed);i++)
     {
      GSHistoryPosition item=closed[i];
      int j=i-1;
      while(j>=0 && (closed[j].last_exit>item.last_exit ||
                     (closed[j].last_exit==item.last_exit && closed[j].last_ticket>item.last_ticket)))
        { closed[j+1]=closed[j]; j--; }
      closed[j+1]=item;
     }
   for(int i=ArraySize(closed)-1;i>=0;i--)
     {
      if(closed[i].net>=-1e-8) break;
      budget.loss_streak++;
     }
   if(budget.entries_today>=MaxEntriesPerDay) return GSReject(reason,"HOLD_DAILY_ENTRY_LIMIT");
   if(budget.loss_streak>=MaxConsecutiveLossesPerDay) return GSReject(reason,"HOLD_DAILY_LOSS_STREAK");
   if(budget.daily_net<=-reference*MaxDailyLossPct/100.0) return GSReject(reason,"HOLD_DAILY_LOSS_LIMIT");
   if(budget.weekly_net<=-reference*MaxWeeklyLossPct/100.0) return GSReject(reason,"HOLD_WEEKLY_LOSS_LIMIT");
   budget.available=GSLossAllowance(reference,equity,EquityShieldMinPctOfReference,
                                   MaxDailyLossPct,MaxWeeklyLossPct,budget.daily_net,budget.weekly_net);
   if(!GSPositive(budget.available)) return GSReject(reason,"HOLD_LOSS_HEADROOM_EXHAUSTED");
   return true;
  }
#endif
