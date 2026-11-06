#ifndef GOLDSHIELD_SETTINGS_MQH
#define GOLDSHIELD_SETTINGS_MQH
#include <GoldShieldDemo20/DomainTypes.mqh>
#include <GoldShieldDemo20/SafetyMath.mqh>

input group "GENERAL - Phase 1, standalone"
input GSExecutionMode ExecutionMode=SHADOW;
input bool EnableAutoTrading=false;
input bool DemoTradingOptIn=false;
input bool AllowRealTrading=false; // Reserved: real execution is blocked in this build.
input string TradeSymbol="XAUUSD";
input ENUM_TIMEFRAMES SignalTimeframe=PERIOD_M15;
input ulong MagicNumber=26011060;
input double CapitalLimitUSD=0.0; // 0=account equity; USD/USC only when capped. Persisted virtual ledger.
input string RequiredAccountCurrency=""; // A Cent preset refuses a USD Standard account.

input group "CLOSED CANDLE RULES - baseline teknis"
input GSSignalModel SignalModel=GS_BASELINE; // Experimental confirmation did not pass comparative testing.
input ENUM_TIMEFRAMES TrendTimeframe=PERIOD_H1;
input double MaxEntryStretchATR=1.0;
input int FastEMAPeriod=20;
input int SlowEMAPeriod=50;
input int RSIPeriod=14;
input bool UseRSIFilter=true;
input int ATRPeriod=14;
input int MinClosedBars=250;
input double StopATRMultiple=2.0;
input double RewardRiskMultiple=2.0;
input double MaxCandleATRMultiple=3.0;
input double MaxGapATRMultiple=1.0;
input int MaxSignalAgeSeconds=120;

input group "BASIC RISK - mata uang akun, bukan selalu USD"
input double BaseLot=0.01; // Maximum requested volume; never rounded up.
input double MaxRiskPerTradePct=0.5;
input double MaxAggregateOpenRiskPct=1.0;
input double MaxTotalAccountLots=0.10; // Raw lots summed across account; not equivalent notionals.
input int MaxAccountPositions=3;
input double MinMarginLevelPct=500.0;
input double MinFreeMarginPct=50.0;
input double RiskBufferPct=25.0;
input double CostBufferPerLot=10.0; // Account currency / lot; illustrative, calibrate per broker.
input double EquityShieldMinPctOfReference=90.0;
input double MaxPositionLossPct=2.0;
input int MaxAllowedSpreadPoints=100; // Illustrative; depends on point size and broker.
input int StaleTickSeconds=15;
input int MaxDeviationPoints=20;
input int CooldownMinutes=30;
input int SessionStartHourServer=0;
input int SessionEndHourServer=24;
input double MaxDailyLossPct=0.5; // Account realized trading P/L, measured against persisted reference.
input double MaxWeeklyLossPct=1.0;
input int MaxConsecutiveLossesPerDay=2; // Owned, fully closed positions after all costs.
input int MaxEntriesPerDay=3; // Unique owned positions; partial fills count once.

input group "FEATURE GATES - belum tersedia pada Phase 1"
input bool GridEnabled=false;
input bool ApiEnabled=false;
input bool TelegramEnabled=false;

input group "OPERATIONS"
input bool EnableChartPanel=true;
input bool ExportResearchBars=false; // Local tester export only; never submits orders or uploads data.

bool GSValidateSettings(string &reason)
  {
   if(ExecutionMode!=DRY_RUN && ExecutionMode!=SHADOW && ExecutionMode!=RULES_DEMO)
      return GSReject(reason,"MODE_NOT_IMPLEMENTED_PHASE1");
   if(AllowRealTrading) return GSReject(reason,"REAL_EXECUTION_UNAVAILABLE_PHASE1");
   if(!MathIsValidNumber(CapitalLimitUSD) || CapitalLimitUSD<0.0)
      return GSReject(reason,"INVALID_CAPITAL_LIMIT");
   if(RequiredAccountCurrency!="" && AccountInfoString(ACCOUNT_CURRENCY)!=RequiredAccountCurrency)
      return GSReject(reason,"EXPECTED_ACCOUNT_CURRENCY_MISMATCH");
   if(GridEnabled || ApiEnabled || TelegramEnabled)
      return GSReject(reason,"FEATURE_NOT_IMPLEMENTED_PHASE1");
   if(TradeSymbol=="" || TradeSymbol!=_Symbol)
      return GSReject(reason,"EXACT_CHART_SYMBOL_REQUIRED");
   if(SignalTimeframe==PERIOD_CURRENT || SignalTimeframe!=_Period ||
      PeriodSeconds(SignalTimeframe)<=0)
      return GSReject(reason,"EXACT_CHART_TIMEFRAME_REQUIRED");
   if(MagicNumber==0 || FastEMAPeriod<2 || SlowEMAPeriod<=FastEMAPeriod ||
      RSIPeriod<2 || ATRPeriod<2 || MinClosedBars<SlowEMAPeriod+ATRPeriod+10)
      return GSReject(reason,"INVALID_INDICATOR_SETTINGS");
   if((SignalModel!=GS_BASELINE && SignalModel!=GS_TREND_PULLBACK) ||
      !GSPositive(MaxEntryStretchATR) ||
      (SignalModel==GS_TREND_PULLBACK && PeriodSeconds(TrendTimeframe)<=PeriodSeconds(SignalTimeframe)))
      return GSReject(reason,"INVALID_TREND_CONFIRMATION_SETTINGS");
   if(!GSPositive(MaxDailyLossPct) || MaxDailyLossPct>1.0 ||
      !GSPositive(MaxWeeklyLossPct) || MaxWeeklyLossPct>2.0 || MaxDailyLossPct>MaxWeeklyLossPct ||
      MaxConsecutiveLossesPerDay<1 || MaxEntriesPerDay<1 || MaxEntriesPerDay>20)
      return GSReject(reason,"INVALID_DAILY_WEEKLY_LIMITS");
   if(!GSPositive(BaseLot) || !GSPositive(StopATRMultiple) ||
      !GSPositive(RewardRiskMultiple) || !GSPositive(MaxCandleATRMultiple) ||
      !GSPositive(MaxGapATRMultiple) || MaxSignalAgeSeconds<1)
      return GSReject(reason,"INVALID_SIGNAL_OR_VOLUME_SETTINGS");
   if(!GSPositive(MaxRiskPerTradePct) || MaxRiskPerTradePct>0.5 ||
      !GSPositive(MaxAggregateOpenRiskPct) || MaxAggregateOpenRiskPct>1.0 ||
      MaxRiskPerTradePct>MaxAggregateOpenRiskPct || !GSPositive(MaxTotalAccountLots) ||
      MaxAccountPositions<1 || !GSPositive(MinMarginLevelPct) || MinMarginLevelPct<100.0 || !GSPositive(MinFreeMarginPct) ||
      MinFreeMarginPct>100.0 || !MathIsValidNumber(RiskBufferPct) || RiskBufferPct<0.0 ||
      !MathIsValidNumber(CostBufferPerLot) || CostBufferPerLot<0.0)
      return GSReject(reason,"INVALID_RISK_SETTINGS");
   if(!GSPositive(EquityShieldMinPctOfReference) || EquityShieldMinPctOfReference>=100.0 ||
      !GSPositive(MaxPositionLossPct) || MaxPositionLossPct>2.0 ||
      MaxAllowedSpreadPoints<1 || StaleTickSeconds<1 || MaxDeviationPoints<0 ||
      CooldownMinutes<1 || SessionStartHourServer<0 || SessionStartHourServer>23 ||
      SessionEndHourServer<1 || SessionEndHourServer>24 ||
      SessionStartHourServer>=SessionEndHourServer)
      return GSReject(reason,"INVALID_PROTECTION_SETTINGS");
   return true;
  }
#endif
