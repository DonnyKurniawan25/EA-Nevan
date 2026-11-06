#ifndef GOLDSHIELD_RESEARCH_EXPORT_MQH
#define GOLDSHIELD_RESEARCH_EXPORT_MQH
#include <GoldShield/Settings.mqh>

// Local raw prices only. Future prices are used later as labels, never live features.
void GSExportResearchBars(const datetime first,const datetime last)
  {
   if(!ExportResearchBars || !MQLInfoInteger(MQL_TESTER) || first<=0 || last<=first) return;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int count=CopyRates(TradeSymbol,SignalTimeframe,first-21*86400,last,rates);
   if(count<=0) { Print("RESEARCH_EXPORT_FAILED rates unavailable"); return; }
   string path="GoldShield\\research_"+IntegerToString((long)MagicNumber)+".csv";
   int file=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE) { Print("RESEARCH_EXPORT_FAILED file unavailable"); return; }
   FileWrite(file,"time_server","open","high","low","close","tick_volume","spread_points","point");
   int written=0;
   for(int i=0;i<count;i++)
     {
      if(rates[i].time+PeriodSeconds(SignalTimeframe)>last) continue;
      FileWrite(file,TimeToString(rates[i].time,TIME_DATE|TIME_SECONDS),rates[i].open,rates[i].high,
                rates[i].low,rates[i].close,rates[i].tick_volume,rates[i].spread,SymbolInfoDouble(TradeSymbol,SYMBOL_POINT));
      written++;
     }
   FileFlush(file); FileClose(file);
   PrintFormat("GOLDSHIELD_RESEARCH_EXPORT closed_bars=%d file=%s",written,path);
  }
#endif
