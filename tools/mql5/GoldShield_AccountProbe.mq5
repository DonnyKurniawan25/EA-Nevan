#property strict
#property description "Read-only account and symbol specification report. No trade requests."

void OnStart(void)
  {
   FolderCreate("GoldShield");
   int file=FileOpen("GoldShield\\account_probe.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE) { Print("ACCOUNT_PROBE_FAILED file"); return; }
   FileWrite(file,"mode","currency","balance","equity","leverage","server","symbol","contract_size",
             "min_lots","point","bid","ask","quote_time","min_spread_cost","min_margin",
             "closed_m15_atr","min_atr_stop_loss","planned_usd10_entry_budget","status");
   string names[]={"XAUUSDc","XAUUSDm","EURUSDc","EURUSDm"};
   string currency=AccountInfoString(ACCOUNT_CURRENCY);
   double units=(currency=="USC" ? 100.0 : (currency=="USD" ? 1.0 : 0.0));
   for(int i=0;i<ArraySize(names);i++)
     {
      string symbol=names[i],status="SYMBOL_UNAVAILABLE";
      double contract=0,volume=0,point=0,spread=-1,margin=-1,atr=-1,stop_loss=-1;
      MqlTick tick; ZeroMemory(tick);
      if(SymbolSelect(symbol,true))
        {
         contract=SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE);
         volume=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
         point=SymbolInfoDouble(symbol,SYMBOL_POINT);
         for(int retry=0;retry<12;retry++)
           {
            if(SymbolInfoTick(symbol,tick) && tick.ask>0 && tick.bid>0) break;
            Sleep(250);
           }
         int handle=iATR(symbol,PERIOD_M15,14);
         if(handle!=INVALID_HANDLE)
           {
            double value[1];
            for(int retry=0;retry<12;retry++)
              {
               if(CopyBuffer(handle,0,1,1,value)==1 && value[0]>0) { atr=value[0]; break; }
               Sleep(250);
              }
            IndicatorRelease(handle);
           }
         double profit=0;
         bool costs=(tick.ask>0 && tick.bid>0 && volume>0 &&
                     OrderCalcProfit(ORDER_TYPE_BUY,symbol,volume,tick.ask,tick.bid,profit));
         if(costs) spread=-profit;
         if(!OrderCalcMargin(ORDER_TYPE_BUY,symbol,volume,tick.ask,margin)) margin=-1;
         if(atr>0 && tick.ask>2*atr && OrderCalcProfit(ORDER_TYPE_BUY,symbol,volume,tick.ask,tick.ask-2*atr,profit))
            stop_loss=-profit;
         status=(costs && margin>=0 ? "READ_ONLY_METADATA_NOT_ORDER_APPROVAL" : "DATA_OR_CONVERSION_UNAVAILABLE");
        }
      FileWrite(file,EnumToString((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)),currency,
                AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),AccountInfoInteger(ACCOUNT_LEVERAGE),
                AccountInfoString(ACCOUNT_SERVER),symbol,contract,volume,point,tick.bid,tick.ask,
                TimeToString(tick.time,TIME_DATE|TIME_SECONDS),spread,margin,atr,stop_loss,10*units*0.005,status);
     }
   FileFlush(file); FileClose(file);
   Print("GOLDSHIELD_ACCOUNT_PROBE_SAVED read-only; no orders sent");
  }
