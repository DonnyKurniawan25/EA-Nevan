#property strict
#property script_show_inputs
#include <GoldShield/SafetyMath.mqh>
#include <GoldShield/Storage.mqh>

int failures=0,checks=0;
void Check(const bool condition,const string name)
  {
   checks++;
   if(!condition) { failures++; Print("FAIL: ",name); }
  }
bool Near(const double a,const double b) { return MathAbs(a-b)<1e-8; }
void OnStart(void)
  {
   Check(Near(GSVolumeDown(0.025,0.01,100,0.01),0.02),"volume rounds down");
   Check(GSVolumeDown(0.009,0.01,100,0.01)==0,"minimum lot not forced");
   Check(Near(GSVolumeDown(0.7,0.25,100,0.25),0.5),"nonstandard volume step");
   Check(GSVolumeDown(-1,0.01,100,0.01)==0,"negative volume rejected");
   Check(GSVolumeDown(1,0.01,100,0)==0,"zero step rejected");
   Check(Near(GSTickDown(2700.129,0.05,2),2700.10),"tick floor");
   Check(Near(GSTickUp(2700.129,0.05,2),2700.15),"tick ceil");
   Check(Near(GSTickDown(2700.1239,0.001,3),2700.123),"three digit quote");
   Check(Near(GSRiskVolume(100,500,25,10,10,0.01,100,0.01),0.15),"risk sizing");
   Check(GSRiskVolume(1,500,25,10,10,0.01,100,0.01)==0,"budget below minimum");
   Check(Near(GSRiskVolume(10000,500,25,10,0.01,0.01,100,0.01),0.01),"base lot cap");
   Check(GSValidStops(true,2700.2,2700,2700.2,2690,2720.6,0.5),"BUY stops");
   Check(GSValidStops(false,2700,2700,2700.2,2710,2680,0.5),"SELL stops");
   Check(!GSValidStops(true,2700.2,2700,2700.2,2700.1,2720,0.5),"BUY stop near spread");
   Check(!GSValidStops(false,2700,2700,2700.2,2700.1,2680,0.5),"SELL stop near spread");
   Check(!GSValidStops(true,2700.2,2700,2700.2,0,2720,0.5),"missing stop");
   Check(GSValidOHLC(2700,2702,2698,2701),"valid candle");
   Check(!GSValidOHLC(2700,2699,2698,2701),"invalid candle");
   Check(GSBaselineSide(2710,2705,2700,55,true)==1,"BUY setup");
   Check(GSBaselineSide(2690,2695,2700,45,true)==-1,"SELL setup");
   Check(GSBaselineSide(2710,2705,2700,80,true)==0,"RSI HOLD");
   Check(GSPreflightCodeOK(0) && GSPreflightCodeOK(10009),"preflight success codes");
   Check(!GSPreflightCodeOK(10019),"not enough money rejected");
   Check(GSTrendPullbackOK(1,105,108,107,102,103,105,100,99,120,115,110,5,1),"confirmed BUY pullback");
   Check(GSTrendPullbackOK(-1,95,92,98,93,97,95,100,101,80,85,90,5,1),"confirmed SELL pullback");
   Check(!GSTrendPullbackOK(1,105,108,107,102,103,105,100,99,105,110,115,5,1),"counter H1 trend veto");
   Check(!GSTrendPullbackOK(1,105,108,109,102,103,105,100,99,120,115,110,5,1),"unbroken high veto");
   Check(!GSTrendPullbackOK(1,105,108,107,104,103,105,100,99,120,115,110,5,1),"no pullback veto");
   Check(!GSTrendPullbackOK(1,105,108,107,102,103,105,100,99,120,115,110,2,1),"extended entry veto");
   Check(!GSTrendPullbackOK(1,105,108,107,102,103,105,100,101,120,115,110,5,1),"falling EMA veto");
   Check(Near(GSLossAllowance(100000,99990,99.9,.03,.075,-16,-16),14),"remaining daily budget");
   Check(Near(GSLossAllowance(100000,100020,99.9,.03,.075,20,20),30),"gains do not enlarge cap");
   Check(Near(GSLossAllowance(100000,99905,99.9,.03,.075,0,-60),5),"remaining shield headroom");
   Check(GSLossAllowance(100000,99900,99.9,.03,.075,0,0)==0,"shield exhaustion");
   Check(GSLossAllowance(100000,100000,99.9,.03,.075,-31,-31)==0,"daily exhaustion");
   Check(GSLossAllowance(100000,100000,99.9,.03,.075,0,-76)==0,"weekly exhaustion");
   Check(Near(GSCapitalLedgerEquity(10,100000,99999),9),"virtual capital tracks loss");
   Check(Near(GSCapitalLedgerEquity(10,100000,110000),10),"profit or deposit never raises cap");
   Check(Near(GSCapitalLedgerEquity(10,100000,99980),-10),"virtual budget never refills");
   Check(GSCapitalLedgerEquity(0,100000,99999)<0,"invalid virtual capital rejects");
   Check(!GSCapitalMarginOK(10,0,20,50,500),"ten dollar margin rejection");
   Check(GSCapitalMarginOK(10,0,1,50,500),"small margin accepted");
   Check(GSCapitalMarginOK(10,1,1,50,500),"existing margin reserved");
   Check(!GSCapitalMarginOK(10,1,1.01,50,500),"margin level threshold");
   Check(!GSCapitalMarginOK(10,0,-1,50,500),"invalid margin rejects");
   for(int i=1;i<=1000;i++)
     {
      double budget=i*0.37,loss=100.0+i*11.0;
      double volume=GSRiskVolume(budget,loss,25,10,0.1,0.01,100,0.01);
      Check(volume*(loss*1.25+10)<=budget+1e-7,"budget property "+IntegerToString(i));
     }
   Check(Near(GSCapitalUnitsUSD(10,"USD"),10),"USD units");
   Check(Near(GSCapitalUnitsUSD(10,"USC"),1000),"USC units not dollars");
   Check(GSCapitalUnitsUSD(10,"EUR")<0,"unknown conversion refused");
   ulong test_magic=900000000000000+(ulong)TimeLocal()*1000+GetMicrosecondCount()%1000;
   GSStorage first_store;
   string storage_reason="";
   Check(first_store.Init(_Symbol,test_magic,storage_reason),"capital test store init");
   Check(first_store.ConfigureCapital(10,storage_reason),"capital first initialization");
   Check(Near(first_store.RiskReference(),10) && Near(first_store.RiskEquity(),10),"virtual budget independent of large demo balance");
   first_store.Release();
   GSStorage resumed_store;
   Check(resumed_store.Init(_Symbol,test_magic,storage_reason) && resumed_store.ConfigureCapital(10,storage_reason),"capital restart same identity");
   Check(Near(resumed_store.RiskReference(),10) && Near(resumed_store.RiskEquity(),10),"capital anchor preserved on restart");
   Check(!resumed_store.ConfigureCapital(20,storage_reason),"raising capital requires review");
   Check(!resumed_store.ConfigureCapital(0,storage_reason),"removing capital guard refused");
   resumed_store.Release();
   FolderCreate("GoldShield");
   int receipt=FileOpen("GoldShield\\unit_last.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(receipt!=INVALID_HANDLE)
     {
      FileWrite(receipt,"checks","failures","time_server");
      FileWrite(receipt,checks,failures,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS));
      FileFlush(receipt); FileClose(receipt);
     }
   PrintFormat("GOLDSHIELD MQL TESTS: checks=%d failures=%d",checks,failures);
  }
