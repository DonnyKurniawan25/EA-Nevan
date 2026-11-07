#property strict
// Read-only account/state observer. Native terminal state is never created here.
input ulong ProbeMagic=0;
input string RequestId="";
input bool WaitForState=true;

string AuditKey()
  {
   string identity=StringFormat("%s|%I64d|%s|%I64u",AccountInfoString(ACCOUNT_SERVER),AccountInfoInteger(ACCOUNT_LOGIN),_Symbol,ProbeMagic);
   uint a=2166136261,b=5381;
   for(int i=0;i<StringLen(identity);i++)
     {
      uint ch=(uint)StringGetCharacter(identity,i);
      a=(a^ch)*16777619;
      b=((b<<5)+b)^ch;
     }
   return StringFormat("GS2.%08X%08X",a,b);
  }

double ReadState(const string key)
  {
   double value=EMPTY_VALUE;
   if(!GlobalVariableCheck(key) || !GlobalVariableGet(key,value)) return EMPTY_VALUE;
   return value;
  }

void OnStart()
  {
   if(ProbeMagic==0 || ProbeMagic>9007199254740991 || StringLen(RequestId)!=64) return;
   string key=AuditKey();
   ulong started=GetTickCount64();
   while(!IsStopped() && GetTickCount64()-started<60000)
     {
      key=AuditKey();
      if(TerminalInfoInteger(TERMINAL_CONNECTED) &&
         (!WaitForState || (GlobalVariableCheck(key+".schema") && GlobalVariableCheck(key+".d20.schema")))) break;
      Sleep(200);
     }
   if(IsStopped()) return;
   bool history_available=HistorySelect(0,TimeTradeServer());
   int matching_history_deals=0;
   if(history_available)
      for(int i=0;i<HistoryDealsTotal();i++)
        {
         ulong deal=HistoryDealGetTicket(i);
         if(deal==0) { history_available=false; break; }
         if(HistoryDealGetString(deal,DEAL_SYMBOL)==_Symbol &&
            (ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)==ProbeMagic) matching_history_deals++;
        }
   bool namespace_present=FileIsExist("GoldShield\\"+key+".lock") || FileIsExist("GoldShield\\"+key+".csv");
   for(int i=0;i<GlobalVariablesTotal() && !namespace_present;i++)
      if(StringFind(GlobalVariableName(i),key+".")==0) namespace_present=true;
   FolderCreate("GoldShield");
   int file=FileOpen("GoldShield\\server_preflight.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE) return;
   FileWrite(file,"nonce","connected","account_mode","margin_mode","server","currency","login","symbol","balance","equity",
             "positions_total","orders_total","account_trade_allowed","account_expert_allowed","terminal_trade_allowed",
             "magic","audit_key","store_schema","reference","trial_schema","entry_submissions","limit","blocked","pending",
             "history_available","matching_history_deals","namespace_present");
   FileWrite(file,RequestId,(int)TerminalInfoInteger(TERMINAL_CONNECTED),
             EnumToString((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)),
             EnumToString((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)),
             AccountInfoString(ACCOUNT_SERVER),AccountInfoString(ACCOUNT_CURRENCY),
             IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)),_Symbol,
             AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),PositionsTotal(),OrdersTotal(),
             (int)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED),(int)AccountInfoInteger(ACCOUNT_TRADE_EXPERT),
             (int)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED),IntegerToString((long)ProbeMagic),key,
             ReadState(key+".schema"),ReadState(key+".reference"),ReadState(key+".d20.schema"),ReadState(key+".d20.used"),
             ReadState(key+".d20.limit"),ReadState(key+".blocked"),ReadState(key+".pending"),
             (int)history_available,matching_history_deals,(int)namespace_present);
   FileFlush(file);
   FileClose(file);
   Print("GoldShield server preflight report saved");
  }
