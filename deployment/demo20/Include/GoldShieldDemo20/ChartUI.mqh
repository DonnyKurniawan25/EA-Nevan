#ifndef GOLDSHIELD_CHART_UI_MQH
#define GOLDSHIELD_CHART_UI_MQH
#include <GoldShieldDemo20/Metrics.mqh>
#include <GoldShieldDemo20/Settings.mqh>
#include <GoldShieldDemo20/DemoTrial.mqh>
#include <GoldShieldDemo20/CapitalGuard.mqh>

void GSDrawPanel(GSStateMachine &state,const GSOwnedPosition &owned,
                 const string last_signal,const string store_key)
  {
   if(!EnableChartPanel) return;
   string account_mode=EnumToString((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE));
   Comment("GOLDSHIELD AI EA V2 | Phase 1 | VALIDASI DEMO BELUM LENGKAP\n",
           "State: ",EnumToString(state.State())," | ",state.Reason(),"\n",
           "Mode: ",EnumToString(ExecutionMode)," | ",account_mode,"\n",
           g_demo20_panel,"\n",
           "Aturan: ",EnumToString(SignalModel),"\n",
           "Simbol: ",TradeSymbol," | ",EnumToString(SignalTimeframe),"\n",
           "Entry: ",(EnableAutoTrading && DemoTradingOptIn && ExecutionMode==RULES_DEMO ? "DEMO OPT-IN" : "NONAKTIF"),"\n",
           "Sinyal: ",last_signal,"\n",
           (g_capital_note=="" ? "" : g_capital_note+"\n"),
           "Balance / equity: ",DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2)," / ",
           DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2)," ",AccountInfoString(ACCOUNT_CURRENCY),"\n",
           "Posisi EA: ",owned.count," | floating + swap (tanpa komisi): ",DoubleToString(owned.floating_pl,2),"\n",
           "Free margin: ",DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE),2),"\n",
           "Grid / ONNX / API / Telegram: BELUM TERSEDIA\n",
           "News: NEWS_FILTER_NOT_CONFIGURED | Sesi: waktu server broker\n",
           "Status persistensi: ",store_key,"\n",
           (ExecutionMode==RULES_DEMO ? "UJI DEMO: entry hanya bila sinyal dan batas risiko lolos." :
                                      "PEMANTAUAN: tidak mengirim permintaan trading."));
  }
#endif
