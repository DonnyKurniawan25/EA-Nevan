#property strict
#include <GoldShieldDemo20/DemoTrial.mqh>
int checks=0,failures=0;
void Check(const bool value,const string label)
  { checks++; if(!value) { failures++; Print("DEMO20 TEST FAIL: ",label); } }
void OnStart(void)
  {
   for(int retry=0;retry<60;retry++)
     {
      if(TerminalInfoInteger(TERMINAL_CONNECTED) && AccountInfoDouble(ACCOUNT_EQUITY)>0.0) break;
      Sleep(250);
     }
   ulong magic=800000000000000+(ulong)TimeLocal()*1000+GetMicrosecondCount()%1000;
   GSStorage first;
   string reason="";
   Check(first.Init(_Symbol,magic,reason),"initialize isolated test storage");
   if(reason!="") Print("DEMO20 storage diagnostic: ",reason);
   Check(GSDemo20Init(first,_Symbol,magic,reason),"arm demo-only limit");
   Check(first.Get(".d20.used")==0,"new trial starts at zero");
   for(int i=1;i<=20;i++)
     {
      Check(GSDemo20Reserve(first,reason),"reserve slot "+IntegerToString(i));
      Check(first.Get(".d20.used")==i,"durable count "+IntegerToString(i));
     }
   Check(!GSDemo20Reserve(first,reason),"21st submission refused");
   Check(first.Get(".d20.used")==20,"rejection does not change count");
   first.Release();
   GSStorage resumed;
   Check(resumed.Init(_Symbol,magic,reason) && GSDemo20Init(resumed,_Symbol,magic,reason),"restart preserves trial");
   Check(resumed.Get(".d20.used")==20 && !GSDemo20CanEnter(resumed,reason),"restart cannot reopen entry allowance");
   GlobalVariableSet(resumed.Key()+".d20.limit",21);
   Check(!GSDemo20Init(resumed,_Symbol,magic,reason) && !GSDemo20CanEnter(resumed,reason),"invalid limit refused");
   resumed.Release();
   FolderCreate("GoldShield");
   int file=FileOpen("GoldShield\\demo20_limit_test.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file!=INVALID_HANDLE)
     {
      FileWrite(file,"checks","failures","orders_sent");
      FileWrite(file,checks,failures,0);
      FileFlush(file); FileClose(file);
     }
   PrintFormat("GOLDSHIELD DEMO20 LIMIT TEST checks=%d failures=%d orders=0",checks,failures);
  }
