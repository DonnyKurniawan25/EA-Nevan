#ifndef GOLDSHIELD_CAPITAL_GUARD_MQH
#define GOLDSHIELD_CAPITAL_GUARD_MQH
#include <GoldShield/Settings.mqh>
#include <GoldShield/Storage.mqh>
#include <GoldShield/SymbolSpec.mqh>

string g_capital_note="";
bool GSConfigureCapital(GSStorage &store,string &reason)
  {
   double units=GSCapitalUnitsUSD(CapitalLimitUSD,AccountInfoString(ACCOUNT_CURRENCY));
   if(units<0.0) return GSReject(reason,"CAPITAL_USD_CONVERSION_UNSUPPORTED");
   return store.ConfigureCapital(units,reason);
  }

void GSAssessCapital(GSSymbolSpec &spec,GSStorage &store)
  {
   if(CapitalLimitUSD<=0.0) { g_capital_note=""; return; }
   string currency=AccountInfoString(ACCOUNT_CURRENCY);
   double equity=store.RiskEquity();
   double budget=MathMax(0.0,equity)*MaxRiskPerTradePct/100.0;
   MqlTick tick;
   double profit=0.0,margin=0.0;
   string status="CAPITAL_DATA_UNAVAILABLE",fresh_reason="";
   double floor_cost=-1.0;
   if(spec.FreshTick(tick,StaleTickSeconds,fresh_reason) &&
      OrderCalcProfit(ORDER_TYPE_BUY,spec.symbol,spec.volume_min,tick.ask,tick.bid,profit) &&
      MathIsValidNumber(profit) && profit<=0.0 &&
      OrderCalcMargin(ORDER_TYPE_BUY,spec.symbol,spec.volume_min,tick.ask,margin) &&
      MathIsValidNumber(margin) && margin>=0.0)
     {
      floor_cost=-profit*(1.0+RiskBufferPct/100.0)+spec.volume_min*CostBufferPerLot;
      status=(floor_cost>budget+1e-8 ? "HOLD_MINIMUM_COST_ABOVE_BUDGET" :
              !GSCapitalMarginOK(equity,AccountInfoDouble(ACCOUNT_MARGIN),margin,MinFreeMarginPct,MinMarginLevelPct) ?
              "HOLD_MINIMUM_MARGIN_ABOVE_BUDGET" : "PRELIMINARY_ONLY_SL_AND_SIGNAL_STILL_REQUIRED");
     }
   g_capital_note=StringFormat("Modal dibatasi %.2f %s | risiko/entry <= %.2f\nBiaya minimum + buffer %.2f | margin minimum %.2f\n%s",
                              equity,currency,budget,floor_cost,margin,status);
   FolderCreate("GoldShield");
   int file=FileOpen("GoldShield\\capital_"+IntegerToString((long)MagicNumber)+".csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file!=INVALID_HANDLE)
     {
      FileWrite(file,"symbol","currency","capital_limit_usd","risk_equity","risk_reference",
                "max_entry_budget","min_lots","min_spread_cost_buffered","min_margin","status");
      FileWrite(file,spec.symbol,currency,CapitalLimitUSD,equity,store.RiskReference(),budget,
                spec.volume_min,floor_cost,margin,status);
      FileFlush(file); FileClose(file);
     }
  }
#endif
