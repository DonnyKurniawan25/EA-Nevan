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
input bool UseHTFTrendFilter=true; // Multi-timeframe trend filter (H1 EMA confirmation)
input ENUM_TIMEFRAMES TrendTimeframe=PERIOD_H1;
input double MaxEntryStretchATR=1.8; // Batas toleransi jarak harga ke EMA (anti-pucuk/lembah)
input int FastEMAPeriod=20;
input int SlowEMAPeriod=50;
input int RSIPeriod=14;
input bool UseRSIFilter=true;
input bool UseADXFilter=true; // Sideways chop filter via ADX
input int ADXPeriod=14; // ADX period
input double ADXThreshold=20.0; // Minimum ADX level to permit entry (below=sideways)
input int ATRPeriod=14;
input int MinClosedBars=250;
input double StopATRMultiple=2.0;
input double RewardRiskMultiple=1.25; // Rasio TP terhadap SL (1.25 = 2.5 ATR target TP runner saat Stop 2.0 ATR)
input double MaxCandleATRMultiple=3.0;
input double MaxGapATRMultiple=1.0;
input int MaxSignalAgeSeconds=120;
input int MaxHoldMinutes=0; // Auto-close profitable trade after N minutes (0=disabled, dynamic market-based exit)
input bool UseEarlyReversalExit=true; // Close position early if M15 candle confirms trend reversal
input bool UseBreakEvenProtection=true; // Protect capital once trade enters profit
input double BreakEvenTriggerATR=0.35; // Profit distance in ATR to activate break-even guard (0.35 ATR = ~$3.2 USD)
input double BreakEvenLockATR=0.05; // Nominal profit yang dikunci saat Break-Even dalam satuan ATR (0.05 ATR = ~$0.5 USD)
input bool UseTrailingStop=true; // Dynamic ATR trailing stop after break-even
input double TrailingStopATR=1.0; // Trailing stop distance behind price in ATR multiples
input double TrailingStepATR=0.3; // Minimum profit advance in ATR to move trailing stop
input double ReversalBufferATR=0.20; // Toleransi buffer penembusan EMA sebelum cut loss (0.20 = 20% ATR)
input double ReversalRSIThreshold=12.0; // Deviasi RSI dari batas netral 50 (BUY cut jika RSI < 38, SELL cut jika RSI > 62)
input bool UsePartialTakeProfit=true; // Amankan profit sebagian di TP 1
input double PartialCloseTriggerATR=1.5; // Jarak profit untuk memicu partial close (1.5 = 1.5 ATR)
input double PartialClosePct=50.0; // Persentase volume yang ditutup di TP 1 (default 50%)
input bool RequireFreshCross=false; // Hanya masuk saat bar baru saja crossover (opsional filter pucuk)
input bool UseCandleDirectionFilter=true; // Sinyal wajib searah candle M15 (BUY hijau, SELL merah)
input double MinCandleClosePercent=50.0; // Tutup candle minimal di 50% range atas (BUY) atau bawah (SELL)
input bool UseTickVolumeFilter=true; // Filter volume candle terhadap rata-rata 5 candle
input double MinTickVolumeRatio=0.75; // Rasio volume minimal dibanding rata-rata 5 candle (0.75 = 75%)
input double MaxTickVolumeRatio=3.0; // Batas atas rasio volume tick terhadap rata-rata (menolak climax / stop-hunt)
input bool UseFridayCloseGuard=true; // Tutup posisi otomatis sebelum bursa Jumat tutup (hindari weekend gap)
input int FridayCloseHourServer=23; // Jam server untuk auto-close Jumat
input int FridayCloseMinuteServer=45; // Menit server untuk auto-close Jumat
input bool RequireSameDirectionMulti=true; // Posisi tambahan (multi-posisi) wajib searah, tolak hedging
input bool RequireProfitForAddOn=true; // Posisi tambahan (multi-posisi) wajib menunggu posisi aktif untung
input double MinAddOnDistanceATR=0.8; // Jarak minimal harga saat ini dari entry posisi aktif dalam ATR
input bool UseMinATRFilter=true; // Tolak entri jika ATR terlalu kecil (pasar mati / likuiditas nol)
input double MinATRPoints=20.0; // Batas minimal ATR dalam points
input double EMAPenetrationBufferATR=0.10; // Buffer penetrasi harga terhadap EMA (0.10 = 10% ATR)
input bool UseSteppedProfitLock=true; // Kunci profit berjenjang (1.5 ATR->+0.5, 2.0 ATR->+1.0, 3.0 ATR->+2.0)
input bool UseRSIProfitProtector=true; // Amankan profit saat RSI mencapai titik jenuh ekstrim
input double RSIExtremeOverbought=75.0; // Level jenuh beli untuk profit taking
input double RSIExtremeOversold=25.0; // Level jenuh jual untuk profit taking
input bool UseDynamicLossCooldown=true; // Jeda ekstra setelah transaksi rugi (hindari whipsaw)
input int LossCooldownMinutes=60; // Durasi cooldown pasca-rugi dalam menit
input bool UseAggressiveRunnerTrailing=true; // Trailing lebih ketat untuk sisa volume setelah TP 1
input double PartialTrailingATR=0.7; // Jarak trailing runner pasca TP 1 dalam kelipatan ATR
input bool RequireHTFSlopeAlignment=true; // Kemiringan EMA tren H1 wajib searah (bukan datar)
input bool RequireRisingADX=false; // Momentum ADX wajib sedang menanjak saat ADX < 25 (hindari perlambatan)
input bool UseCandleBodyFilter=true; // Filter bobot badan candle M15 terhadap rentang total
input double MinCandleBodyRatio=0.40; // Rasio badan minimal (0.40 = 40% dari high-low, tolak doji tipis)
input bool UseRSIMomentumThreshold=true; // Filter deviasi momentum RSI menjauhi garis tengah 50
input double RSIMomentumThreshold=2.0; // Deviasi minimal RSI dari 50 (BUY >= 52, SELL <= 48)
input bool UseAdaptiveADXTrailing=true; // Trailing adaptif responsif saat tren ADX rendah (< 25)
input double AdaptiveLowADXTrailingATR=0.8; // Jarak trailing saat ADX < 25 dalam kelipatan ATR (0.8 ATR)
input bool UseMultiSetup=true; // Aktifkan multi-setup (Crossover, Pullback Retest, Box Breakout)
input bool EnableSetupCrossover=true; // Setup A: Baseline Crossover EMA 20/50
input bool EnableSetupPullback=true; // Setup B: Pullback / Retest EMA 20 di dalam tren kuat
input bool EnableSetupBreakout=true; // Setup C: Breakout Range Lilin 4-Bar + Volume Surge
input bool UseDailyProfitLock=true; // Kunci kemenangan harian: berhenti buka posisi baru jika target harian tercapai
input double DailyProfitTargetPct=2.0; // Target profit harian dalam % dari modal (2.0 = 2%)
input double DailyProfitTargetUSD=0.0; // Target profit harian alternatif dalam USD (0 = gunakan %)
input bool UseWeeklyOpenGuard=true; // Blokir entri 30 menit awal pembukaan bursa emas (anti-gap & spread)
input int WeeklyOpenWaitMinutes=30; // Menit tunggu setelah pembukaan bursa Senin (00:00 - 00:30)
input bool SpreadFreezeOnTrailing=true; // Bekukan modifikasi trailing stop jika spread sedang melebar tajam
input double MaxNewsCandleATRMultiple=2.5; // Batas rentang candle M15 vs ATR (deteksi lonjakan berita ekstrim)
input bool UseMidnightProfitClose=true; // Kunci profit floating sebelum rollover tengah malam (non-kripto)
input int MidnightCloseMinuteServer=50; // Menit server kunci profit sebelum rollover tengah malam (23:50)
input bool UseConfluenceScoring=true; // Aktifkan evaluasi skor konfluensi terbobot multi-aturan
input int MinConfluenceScore=65; // Ambang minimal skor konfluensi untuk validasi order (default: 65 poin)
input bool UseVolatilityExpansionTP=true; // Perlebar TP runner ke 3.5 ATR saat tren kencang (ADX >= 30)
input bool UseAcceleratorTrailing=true; // Trailing akselerator agresif kunci laba cepat anti-koreksi
input bool RequireBreakEvenForAddOn=true; // Zero-risk pyramiding: posisi ke-2 hanya jika posisi 1 sudah lock BE

input group "BASIC RISK - mata uang akun, bukan selalu USD"
input double BaseLot=0.05; // Maximum requested volume; never rounded up.
input bool   UseAutoLotByRisk=false; // Hitung lot dinamis berbasis toleransi risiko modal (MaxRiskPerTradePct & jarak SL)
input double MaxLotPerTrade=0.05;    // Batas lot maksimum per posisi saat UseAutoLotByRisk aktif
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
input bool UseSessionFilter=false; // Filter jendela jam sesi trading aktif
input bool BlockMidnightRollover=true; // Blokir entri saat rollover broker
input int RolloverStartMinute=55; // Menit mulai blokir rollover (23:55)
input int RolloverEndMinute=15; // Menit selesai blokir rollover (00:15)
input bool UseSpreadATRFilter=true; // Filter pelebaran spread dinamis terhadap ATR
input double MaxSpreadATRMultiple=0.30; // Toleransi spread maksimal (% dari ATR M15, 0.30 = 30%)
input double MaxDailyLossPct=0.5; // Account realized trading P/L, measured against persisted reference.
input double MaxWeeklyLossPct=1.0;
input int MaxConsecutiveLossesPerDay=2; // Owned, fully closed positions after all costs.
input int MaxEntriesPerDay=3; // Unique owned positions; partial fills count once.
input bool UseDynamicDailyQuota=true; // Kuota dinamis: terus jika untung/impas, batasi ketat jika rugi
input int MaxDynamicEntriesPerDay=10; // Batas absolut entri per hari saat mode kuota dinamis

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
      ((SignalModel==GS_TREND_PULLBACK || UseHTFTrendFilter) && PeriodSeconds(TrendTimeframe)<=PeriodSeconds(SignalTimeframe)))
      return GSReject(reason,"INVALID_TREND_CONFIRMATION_SETTINGS");
   if(UseADXFilter && (ADXPeriod<2 || !GSPositive(ADXThreshold) || ADXThreshold>100.0))
      return GSReject(reason,"INVALID_ADX_SETTINGS");
   if(!GSPositive(MaxDailyLossPct) || MaxDailyLossPct>1.0 ||
      !GSPositive(MaxWeeklyLossPct) || MaxWeeklyLossPct>2.0 || MaxDailyLossPct>MaxWeeklyLossPct ||
      MaxConsecutiveLossesPerDay<1 || MaxEntriesPerDay<1 || MaxEntriesPerDay>20)
      return GSReject(reason,"INVALID_DAILY_WEEKLY_LIMITS");
   if(!GSPositive(BaseLot) || !GSPositive(StopATRMultiple) ||
      !GSPositive(RewardRiskMultiple) || !GSPositive(MaxCandleATRMultiple) ||
      !GSPositive(MaxGapATRMultiple) || MaxSignalAgeSeconds<1 || MaxHoldMinutes<0 ||
      !GSPositive(BreakEvenTriggerATR) ||
      (UseTrailingStop && (!GSPositive(TrailingStopATR) || !GSPositive(TrailingStepATR))))
      return GSReject(reason,"INVALID_SIGNAL_OR_VOLUME_SETTINGS");
   if(!GSPositive(MaxRiskPerTradePct) || MaxRiskPerTradePct>0.5 ||
      !GSPositive(MaxAggregateOpenRiskPct) || MaxAggregateOpenRiskPct>1.0 ||
      MaxRiskPerTradePct>MaxAggregateOpenRiskPct || !GSPositive(MaxTotalAccountLots) ||
      MaxAccountPositions<1 || !GSPositive(MinMarginLevelPct) || MinMarginLevelPct<100.0 || !GSPositive(MinFreeMarginPct) ||
      MinFreeMarginPct>100.0 || !MathIsValidNumber(RiskBufferPct) || RiskBufferPct<0.0 ||
      !MathIsValidNumber(CostBufferPerLot) || CostBufferPerLot<0.0)
      return GSReject(reason,"INVALID_RISK_SETTINGS");
   if(UseAutoLotByRisk && (!GSPositive(MaxLotPerTrade) || MaxLotPerTrade>MaxTotalAccountLots))
      return GSReject(reason,"INVALID_AUTO_LOT_SETTINGS");
   if(!GSPositive(EquityShieldMinPctOfReference) || EquityShieldMinPctOfReference>=100.0 ||
      !GSPositive(MaxPositionLossPct) || MaxPositionLossPct>2.0 ||
      MaxAllowedSpreadPoints<1 || StaleTickSeconds<1 || MaxDeviationPoints<0 ||
      CooldownMinutes<1 || SessionStartHourServer<0 || SessionStartHourServer>23 ||
      SessionEndHourServer<1 || SessionEndHourServer>24 ||
      SessionStartHourServer>=SessionEndHourServer ||
      !GSPositive(MaxSpreadATRMultiple) || MaxSpreadATRMultiple>2.0 ||
      RolloverStartMinute<0 || RolloverStartMinute>59 ||
      RolloverEndMinute<0 || RolloverEndMinute>59 ||
      MaxDynamicEntriesPerDay<1 || MaxDynamicEntriesPerDay>50 ||
      ReversalBufferATR<0.0 || ReversalBufferATR>1.0 ||
      ReversalRSIThreshold<0.0 || ReversalRSIThreshold>25.0 ||
      !GSPositive(PartialCloseTriggerATR) ||
      PartialClosePct<=0.0 || PartialClosePct>=100.0 ||
      MinCandleClosePercent<10.0 || MinCandleClosePercent>90.0 ||
      MinTickVolumeRatio<0.1 || MinTickVolumeRatio>3.0 ||
      MaxTickVolumeRatio<0.0 || MaxTickVolumeRatio>10.0 ||
      BreakEvenLockATR<0.0 || BreakEvenLockATR>1.0 ||
      MinAddOnDistanceATR<0.0 || MinAddOnDistanceATR>5.0 ||
      FridayCloseHourServer<0 || FridayCloseHourServer>23 ||
      FridayCloseMinuteServer<0 || FridayCloseMinuteServer>59 ||
      MinATRPoints<0.0 || EMAPenetrationBufferATR<0.0 || EMAPenetrationBufferATR>1.0 ||
      RSIExtremeOverbought<=50.0 || RSIExtremeOverbought>=100.0 ||
      RSIExtremeOversold<=0.0 || RSIExtremeOversold>=50.0 ||
      MinCandleBodyRatio<0.0 || MinCandleBodyRatio>0.90 ||
      RSIMomentumThreshold<0.0 || RSIMomentumThreshold>10.0 ||
      !GSPositive(AdaptiveLowADXTrailingATR) ||
      !GSPositive(MaxNewsCandleATRMultiple) ||
      DailyProfitTargetPct<0.0 || DailyProfitTargetPct>50.0 ||
      DailyProfitTargetUSD<0.0 || WeeklyOpenWaitMinutes<0 || WeeklyOpenWaitMinutes>120 ||
      MidnightCloseMinuteServer<0 || MidnightCloseMinuteServer>59 ||
      MinConfluenceScore<10 || MinConfluenceScore>100 ||
      LossCooldownMinutes<1 || !GSPositive(PartialTrailingATR))
      return GSReject(reason,"INVALID_PROTECTION_SETTINGS");
   return true;
  }
#endif
