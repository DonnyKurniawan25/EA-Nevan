#ifndef GOLDSHIELD_DEMO20_TRIAL_MQH
#define GOLDSHIELD_DEMO20_TRIAL_MQH
#include <GoldShieldDemo20/Settings.mqh>
#include <GoldShieldDemo20/Storage.mqh>
#include <GoldShieldDemo20/Metrics.mqh>

const int GS_DEMO20_LIMIT=20;
struct GS20Position { long id; double incoming,outgoing,net; };
string g_demo20_panel="Uji DEMO: maksimum 20 pengiriman entry";

bool GS20History(const string symbol,const ulong magic,int &entries,int &closed,int &wins,int &losses,double &net)
  {
   entries=0; closed=0; wins=0; losses=0; net=0;
   if(!HistorySelect(0,TimeTradeServer())) return false;
   GS20Position positions[];
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) return false;
      if(HistoryDealGetString(ticket,DEAL_SYMBOL)!=symbol || (ulong)HistoryDealGetInteger(ticket,DEAL_MAGIC)!=magic) continue;
      long type=HistoryDealGetInteger(ticket,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      long id=HistoryDealGetInteger(ticket,DEAL_POSITION_ID);
      double volume=HistoryDealGetDouble(ticket,DEAL_VOLUME);
      long entry=HistoryDealGetInteger(ticket,DEAL_ENTRY);
      if(id<=0 || !GSPositive(volume) || (entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY)) return false;
      int index=-1;
      for(int j=0;j<ArraySize(positions);j++) if(positions[j].id==id) { index=j; break; }
      if(index<0)
        {
         index=ArraySize(positions);
         if(ArrayResize(positions,index+1)!=index+1) return false;
         ZeroMemory(positions[index]); positions[index].id=id;
        }
      if(entry==DEAL_ENTRY_IN) positions[index].incoming+=volume;
      else positions[index].outgoing+=volume;
      positions[index].net+=HistoryDealGetDouble(ticket,DEAL_PROFIT)+HistoryDealGetDouble(ticket,DEAL_COMMISSION)+
                            HistoryDealGetDouble(ticket,DEAL_SWAP)+HistoryDealGetDouble(ticket,DEAL_FEE);
     }
   for(int i=0;i<ArraySize(positions);i++)
     {
      if(positions[i].outgoing>positions[i].incoming+1e-8) return false;
      if(positions[i].incoming>0) entries++;
      if(positions[i].incoming<=0 || MathAbs(positions[i].incoming-positions[i].outgoing)>1e-8) continue;
      if(!MathIsValidNumber(positions[i].net)) return false;
      closed++; net+=positions[i].net;
      if(positions[i].net>1e-8) wins++;
      else if(positions[i].net< -1e-8) losses++;
     }
   return true;
  }

bool GS20Put(const string key,const double value)
  {
   if(GlobalVariableSet(key,value)==0) return false;
   GlobalVariablesFlush();
   double actual=0;
   return GlobalVariableGet(key,actual) && actual==value;
  }

bool GSDemo20Init(GSStorage &store,const string symbol,const ulong magic,string &reason)
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
      return GSReject(reason,"DEMO20_REFUSES_ALL_REAL_ACCOUNTS");
   int entries,closed,wins,losses; double net;
   if(!GS20History(symbol,magic,entries,closed,wins,losses,net)) return GSReject(reason,"DEMO20_HISTORY_UNAVAILABLE");
   if(entries>GS_DEMO20_LIMIT) return GSReject(reason,"DEMO20_HISTORY_EXCEEDS_LIMIT");
   string base=store.Key()+".d20";
   if(!GlobalVariableCheck(base+".schema"))
     {
      if(GlobalVariableCheck(base+".used") || GlobalVariableCheck(base+".limit"))
         return GSReject(reason,"DEMO20_PARTIAL_STATE_REVIEW_REQUIRED");
      if(entries>GS_DEMO20_LIMIT || !GS20Put(base+".used",entries) || !GS20Put(base+".limit",GS_DEMO20_LIMIT) ||
         !GS20Put(base+".schema",1)) return GSReject(reason,"DEMO20_STATE_INITIALIZATION_FAILED");
     }
   double used=store.Get(".d20.used");
   if(store.Get(".d20.schema")!=1 || store.Get(".d20.limit")!=GS_DEMO20_LIMIT ||
      !MathIsValidNumber(used) || used<0 || used>GS_DEMO20_LIMIT || MathFloor(used)!=used)
      return GSReject(reason,"DEMO20_INVALID_LIMIT_STATE");
   if(entries>used && !GS20Put(base+".used",entries)) return GSReject(reason,"DEMO20_HISTORY_SYNC_FAILED");
   return true;
  }

bool GSDemo20CanEnter(GSStorage &store,string &reason)
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO ||
      store.Get(".d20.schema")!=1 || store.Get(".d20.limit")!=GS_DEMO20_LIMIT)
      return GSReject(reason,"DEMO20_ACCOUNT_OR_LIMIT_INVALID");
   double used=store.Get(".d20.used");
   if(!MathIsValidNumber(used) || used<0 || MathFloor(used)!=used)
      return GSReject(reason,"DEMO20_COUNTER_INVALID");
   if(used>=GS_DEMO20_LIMIT) return GSReject(reason,"DEMO20_LIMIT_REACHED_NO_MORE_ENTRIES");
   return true;
  }

bool GSDemo20Reserve(GSStorage &store,string &reason)
  {
   if(!GSDemo20CanEnter(store,reason)) return false;
   double used=store.Get(".d20.used");
   string key=store.Key()+".d20.used";
   if(!GlobalVariableSetOnCondition(key,used+1,used)) return GSReject(reason,"DEMO20_SLOT_RESERVATION_FAILED");
   GlobalVariablesFlush();
   if(store.Get(".d20.used")!=used+1) return GSReject(reason,"DEMO20_SLOT_VERIFY_FAILED");
   return true;
  }

void GSDemo20Status(GSStorage &store,const GSOwnedPosition &owned,GSStateMachine &state)
  {
   static datetime last=0;
   static string signature="";
   static bool complete=false;
   if(complete && owned.count==0 && store.Get(".d20.used")>=GS_DEMO20_LIMIT) return;
   datetime now=TimeTradeServer();
   if(now==last) return;
   last=now;
   int entries,closed,wins,losses; double net;
   bool history=GS20History(TradeSymbol,MagicNumber,entries,closed,wins,losses,net);
   int used=(int)store.Get(".d20.used");
   string trial=(used>=GS_DEMO20_LIMIT ? (owned.count>0 ? "LIMIT_REACHED_MANAGING_LAST_POSITION" : "LIMIT_REACHED_FLAT") : "RUNNING_WAIT_VALID_SIGNAL");
   if(!history) trial="HISTORY_UNAVAILABLE_REVIEW_REQUIRED";
   g_demo20_panel=StringFormat("UJI DEMO: %d/20 pengiriman | %d selesai | menang %d / rugi %d\nNet tertutup %.2f %s | %s",
                             used,closed,wins,losses,net,AccountInfoString(ACCOUNT_CURRENCY),trial);
   string next=StringFormat("%d|%d|%d|%d|%s|%s",used,closed,wins,owned.count,EnumToString(state.State()),state.Reason());
   if(next==signature) return;
   signature=next;
   int file=FileOpen("GoldShield\\demo20_"+IntegerToString((long)MagicNumber)+".csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE) return;
   FileWrite(file,"time_server","account_mode","symbol","limit","entry_submissions","filled_positions","closed_positions",
             "wins","losses","net_closed","currency","open_positions","trial_status","core_state","core_reason");
   FileWrite(file,TimeToString(now,TIME_DATE|TIME_SECONDS),"DEMO",TradeSymbol,GS_DEMO20_LIMIT,used,entries,closed,
             wins,losses,net,AccountInfoString(ACCOUNT_CURRENCY),owned.count,trial,EnumToString(state.State()),state.Reason());
   FileFlush(file); FileClose(file);

   int acc_file=FileOpen("GoldShield\\account_live.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(acc_file!=INVALID_HANDLE)
     {
      FileWrite(acc_file,"time_server","balance","equity","currency","open_positions");
      FileWrite(acc_file,TimeToString(now,TIME_DATE|TIME_SECONDS),
                DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2),
                DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2),
                AccountInfoString(ACCOUNT_CURRENCY),IntegerToString(owned.count));
      FileFlush(acc_file); FileClose(acc_file);
     }
   if(used>=GS_DEMO20_LIMIT && closed>=GS_DEMO20_LIMIT && owned.count==0) complete=true;
  }
#endif
