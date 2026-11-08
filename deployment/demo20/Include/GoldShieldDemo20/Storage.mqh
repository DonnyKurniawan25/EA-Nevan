#ifndef GOLDSHIELD_STORAGE_MQH
#define GOLDSHIELD_STORAGE_MQH
#include <GoldShieldDemo20/DomainTypes.mqh>
#include <GoldShieldDemo20/SafetyMath.mqh>

double GSCapitalUnitsUSD(const double usd,const string currency)
  {
   if(!MathIsValidNumber(usd) || usd<0.0) return -1.0;
   if(usd==0.0) return 0.0;
   if(currency=="USD") return usd;
   if(currency=="USC") return usd*100.0;
   return -1.0; // Never guess the value of a different account currency.
  }

class GSStorage
  {
private:
   string m_key;
   int m_lock;
   bool Put(const string suffix,const double value)
     {
      if(GlobalVariableSet(m_key+suffix,value)==0) return false;
      GlobalVariablesFlush();
      double stored=0.0;
      return GlobalVariableGet(m_key+suffix,stored) && stored==value;
     }
public:
   GSStorage(void) { m_lock=INVALID_HANDLE; }
   bool Set(const string suffix,const double value) { return Put(suffix,value); }
   string Key(void) { return m_key; }
   double Get(const string suffix)
     {
      double value=0.0;
      if(!GlobalVariableGet(m_key+suffix,value)) return EMPTY_VALUE;
      return value;
     }
   bool Init(const string symbol,const ulong magic,string &reason)
     {
      // Two hashes keep keys short and avoid writing account IDs into filenames/logs.
      string identity=StringFormat("%s|%I64d|%s|%I64u",AccountInfoString(ACCOUNT_SERVER),
                                   AccountInfoInteger(ACCOUNT_LOGIN),symbol,magic);
      uint a=2166136261,b=5381;
      for(int i=0;i<StringLen(identity);i++)
        {
         uint ch=(uint)StringGetCharacter(identity,i);
         a=(a^ch)*16777619;
         b=((b<<5)+b)^ch;
        }
      m_key=StringFormat("GS2.%08X%08X",a,b);
      FolderCreate("GoldShield");
      ResetLastError(); // An existing directory is normal. FileOpen is authoritative.
      // No FILE_SHARE_* flags: a second chart with this account/symbol/magic is refused.
      m_lock=FileOpen("GoldShield\\"+m_key+".lock",FILE_READ|FILE_WRITE|FILE_BIN);
      if(m_lock==INVALID_HANDLE) return GSReject(reason,"INSTANCE_LOCK_UNAVAILABLE");
      if(!GlobalVariableCheck(m_key+".schema"))
        {
         if(FileSize(m_lock)>0) return GSReject(reason,"PERSISTENT_GLOBALS_MISSING_REVIEW_REQUIRED");
         // Write schema last. A partially initialized store is never accepted as valid.
         if(!Put(".bar",0) || !Put(".pending",0) || !Put(".blocked",0) ||
            !Put(".cooldown",0) || !Put(".close_tries",0) ||
            !Put(".close_time",0) || !Put(".reference",AccountInfoDouble(ACCOUNT_EQUITY)) ||
            !Put(".schema",1)) return GSReject(reason,"STORAGE_INITIALIZATION_FAILED");
        }
      if(Get(".schema")!=1 || !GSPositive(Get(".reference")) ||
         Get(".reference")==EMPTY_VALUE ||
         !MathIsValidNumber(Get(".bar")) || Get(".bar")==EMPTY_VALUE || Get(".bar")<0 ||
         Get(".pending")==EMPTY_VALUE || Get(".blocked")==EMPTY_VALUE ||
         Get(".cooldown")==EMPTY_VALUE || Get(".close_tries")==EMPTY_VALUE ||
         Get(".close_time")==EMPTY_VALUE)
         return GSReject(reason,"STORAGE_INVALID_REQUIRES_REVIEW");
      if(Get(".blocked")<0.0 || Get(".blocked")>2.0 || Get(".cooldown")<0.0 ||
         Get(".close_tries")<0.0 || Get(".close_tries")>3.0 || Get(".close_time")<0.0 ||
         !MathIsValidNumber(Get(".pending")) || Get(".pending")< -1.0)
         return GSReject(reason,"STORAGE_VALUE_RANGE_INVALID");
      FileSeek(m_lock,0,SEEK_SET);
      if(FileWriteInteger(m_lock,1,INT_VALUE)==0) return GSReject(reason,"STATE_SENTINEL_WRITE_FAILED");
      FileFlush(m_lock);
      return true;
     }
   void Release(void)
     {
      if(m_lock!=INVALID_HANDLE) FileClose(m_lock);
      m_lock=INVALID_HANDLE;
     }
   bool ConfigureCapital(const double requested,string &reason)
     {
      bool exists=GlobalVariableCheck(m_key+".cap_schema");
      if(requested==0.0)
        {
         if(exists || GlobalVariableCheck(m_key+".cap_anchor"))
            return GSReject(reason,"CAPITAL_GUARD_REMOVAL_REQUIRES_REVIEW");
         return true;
        }
      if(!GSPositive(requested)) return GSReject(reason,"CAPITAL_UNITS_UNSUPPORTED");
      if(!exists)
        {
         if(GlobalVariableCheck(m_key+".cap_anchor") || GlobalVariableCheck(m_key+".cap_amount"))
            return GSReject(reason,"CAPITAL_STORE_PARTIAL_REVIEW_REQUIRED");
         double actual=AccountInfoDouble(ACCOUNT_EQUITY);
         if(!GSPositive(actual) || !Put(".cap_anchor",actual) ||
            !Put(".cap_amount",MathMin(requested,actual)) || !Put(".cap_request",requested) ||
            !Put(".cap_schema",1.0)) return GSReject(reason,"CAPITAL_STORE_WRITE_FAILED");
        }
      if(Get(".cap_schema")!=1.0 || Get(".cap_request")!=requested ||
         Get(".cap_amount")==EMPTY_VALUE || Get(".cap_anchor")==EMPTY_VALUE ||
         !GSPositive(Get(".cap_amount")) || !GSPositive(Get(".cap_anchor")))
         return GSReject(reason,"CAPITAL_CONFIG_CHANGED_OR_INVALID_REVIEW_REQUIRED");
      return true;
     }
   double RiskReference(void)
     { return (GlobalVariableCheck(m_key+".cap_schema") ? Get(".cap_amount") : Get(".reference")); }
   double RiskEquity(void)
     {
      double actual=AccountInfoDouble(ACCOUNT_EQUITY);
      if(!GlobalVariableCheck(m_key+".cap_schema")) return actual;
      return GSCapitalLedgerEquity(Get(".cap_amount"),Get(".cap_anchor"),actual);
     }
   bool ConsumeBar(const datetime candle)
     {
      double last=Get(".bar");
      if(last==EMPTY_VALUE || candle<=last) return false;
      return Put(".bar",(double)candle);
     }
   bool BeginEntry(const datetime candle)
     {
      return Get(".pending")==0.0 && Get(".blocked")==0.0 &&
             Put(".pending",(double)candle);
     }
   bool ConfirmEntry(const string broker_comment)
     {
      double pending=Get(".pending");
      if(pending<=0 || pending==EMPTY_VALUE) return false;
      // Comments may be changed by a broker. Ambiguity remains blocked for operator review.
      string expected="GS2|"+IntegerToString((long)pending);
      if(broker_comment!=expected) return false;
      return Put(".pending",0.0);
     }
   bool Block(const bool emergency=false)
     {
      return Put(".blocked",(emergency || Get(".blocked")==2.0 ? 2.0 : 1.0));
     }
   bool BeginClose(void)
     {
      // Keep an ambiguous entry intent intact, but never let it prevent a verified ticket's risk exit.
      double pending=Get(".pending");
      if(pending==EMPTY_VALUE || !MathIsValidNumber(pending)) return false;
      if(pending>0.0) return true;
      // Negative pending marks an exit when no uncertain entry needs to be preserved.
      return Put(".pending",-1.0);
     }
   bool RecordCloseAttempt(void)
     {
      double tries=Get(".close_tries");
      return tries>=0.0 && tries<3.0 && Put(".close_tries",tries+1.0) &&
             Put(".close_time",(double)TimeTradeServer());
     }
   bool FinishClose(const datetime cooldown_until)
     {
      return Put(".cooldown",(double)cooldown_until) && Put(".close_tries",0.0) &&
             Put(".close_time",0.0) && Put(".pending",0.0);
     }
   bool SetCooldown(const datetime until) { return Put(".cooldown",(double)until); }
  };
#endif
