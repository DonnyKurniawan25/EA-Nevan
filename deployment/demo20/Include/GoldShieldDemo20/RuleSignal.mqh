#ifndef GOLDSHIELD_RULE_SIGNAL_MQH
#define GOLDSHIELD_RULE_SIGNAL_MQH
#include <GoldShieldDemo20/DomainTypes.mqh>
#include <GoldShieldDemo20/Settings.mqh>

GSSide GSEvaluateRules(const GSMarketSnapshot &data,const MqlTick &tick,string &reason)
  {
   if(TimeCurrent()<data.available_at_server ||
      TimeCurrent()-data.available_at_server>MaxSignalAgeSeconds)
     { reason="HOLD_SIGNAL_TOO_OLD_OR_CLOCK"; return GS_HOLD; }
   if(data.bar.high-data.bar.low>data.atr*MaxNewsCandleATRMultiple)
     { reason="HOLD_NEWS_VOLATILITY_SURGE"; return GS_HOLD; }
   if(MathAbs(data.bar.open-data.previous.close)>data.atr*MaxGapATRMultiple ||
      MathAbs(tick.bid-data.bar.close)>data.atr*MaxGapATRMultiple)
     { reason="HOLD_GAP_OR_SLIPPAGE"; return GS_HOLD; }

   // Prioritas 2: Filter sideways / konsolidasi via ADX
   if(UseADXFilter)
     {
      if(!MathIsValidNumber(data.adx) || data.adx<0.0)
        { reason="HOLD_ADX_DATA_INVALID"; return GS_HOLD; }
      if(data.adx<ADXThreshold)
        { reason="HOLD_ADX_SIDEWAYS"; return GS_HOLD; }
      // Pengimbang ADX rendah (20-25): momentum wajib sedang menguat (ADX menanjak)
      if(RequireRisingADX && data.adx<25.0 && GSPositive(data.previous_adx))
        {
         if(data.adx<=data.previous_adx)
           { reason="HOLD_ADX_MOMENTUM_FALLING"; return GS_HOLD; }
        }
     }

   // Filter likuiditas pasar mati via Min ATR
   if(UseMinATRFilter && GSPositive(MinATRPoints))
     {
      double min_atr=MinATRPoints*_Point;
      if(data.atr<min_atr)
        { reason="HOLD_ATR_TOO_LOW_DEAD_MARKET"; return GS_HOLD; }
     }

   int side=0;
   string candidate_setup="";

   if(UseMultiSetup)
     {
      // Model 1: Pullback / Retest EMA 20 di dalam tren kuat (Prioritas Utama: Risk-to-Reward Terbaik)
      if(EnableSetupPullback)
        {
         double pullback_zone = GSPositive(data.atr) ? (data.atr * 0.15) : 0.0;
         // BUY: Struktur Uptrend (Fast > Slow), lilin sempat uji support EMA (toleransi 0.15 ATR) lalu memantul tutup hijau
         if(data.fast_ema > data.slow_ema && data.fast_ema >= data.previous_fast_ema &&
            (data.previous.low <= data.previous_fast_ema + pullback_zone || data.bar.low <= data.fast_ema + pullback_zone) &&
            data.bar.close > data.fast_ema && data.bar.close > data.bar.open &&
            (!UseRSIFilter || (data.rsi >= 48.0 && data.rsi <= 75.0)))
           {
            side = 1;
            candidate_setup = "SETUP_PULLBACK";
           }
         // SELL: Struktur Downtrend (Fast < Slow), lilin sempat uji resistensi EMA (toleransi 0.15 ATR) lalu ditolak tutup merah
         else if(data.fast_ema < data.slow_ema && data.fast_ema <= data.previous_fast_ema &&
                 (data.previous.high >= data.previous_fast_ema - pullback_zone || data.bar.high >= data.fast_ema - pullback_zone) &&
                 data.bar.close < data.fast_ema && data.bar.close < data.bar.open &&
                 (!UseRSIFilter || (data.rsi >= 25.0 && data.rsi <= 52.0)))
           {
            side = -1;
            candidate_setup = "SETUP_PULLBACK";
           }
        }

      // Model 2: Box / Range Breakout 4-Bar dengan lonjakan momentum & volume
      if(side==0 && EnableSetupBreakout)
        {
         // BUY: Menembus High 4 lilin sebelumnya, ditutup hijau di atas EMA
         if(data.breakout_high > 0.0 && data.bar.close > data.breakout_high &&
            data.bar.close > data.bar.open && data.fast_ema > data.slow_ema &&
            (!UseRSIFilter || (data.rsi >= 50.0 && data.rsi <= 78.0)))
           {
            side = 1;
            candidate_setup = "SETUP_BREAKOUT";
           }
         // SELL: Menembus Low 4 lilin sebelumnya, ditutup merah di bawah EMA
         else if(data.breakout_low > 0.0 && data.bar.close < data.breakout_low &&
                 data.bar.close < data.bar.open && data.fast_ema < data.slow_ema &&
                 (!UseRSIFilter || (data.rsi >= 22.0 && data.rsi <= 50.0)))
           {
            side = -1;
            candidate_setup = "SETUP_BREAKOUT";
           }
        }

      // Model 3: Baseline EMA Crossover
      if(side==0 && EnableSetupCrossover)
        {
         int base_side = GSBaselineSide(data.bar.close, data.fast_ema, data.slow_ema, data.rsi, UseRSIFilter);
         if(base_side != 0)
           {
            side = base_side;
            candidate_setup = "SETUP_CROSSOVER";
           }
        }
     }
   else
     {
      side = GSBaselineSide(data.bar.close, data.fast_ema, data.slow_ema, data.rsi, UseRSIFilter);
      candidate_setup = "SETUP_CROSSOVER";
     }

   if(side==0)
     {
      reason="HOLD_RULES_NO_SETUP";
      return GS_HOLD;
     }

   // 1. HARD SAFETY GATES (Pelindung Modal Mutlak - Tidak Boleh Dilanggar)
   // Filter anti-chasing: tolak entry jika harga sudah lonjak terlalu jauh dari EMA (pucuk/lembah)
   if(GSPositive(MaxEntryStretchATR) && GSPositive(data.atr))
     {
      double max_stretch=data.atr*MaxEntryStretchATR;
      if(MathAbs(data.bar.close-data.fast_ema)>max_stretch)
        { reason="HOLD_PRICE_OVEREXTENDED"; return GS_HOLD; }
     }

   // Filter anti-climax volume: tolak jika volume meledak liar > 3x (stop-hunt institusi)
   if(UseTickVolumeFilter && MaxTickVolumeRatio>0.0 && data.avg_tick_volume>0.0 &&
      (double)data.bar.tick_volume>data.avg_tick_volume*MaxTickVolumeRatio)
     {
      reason="HOLD_VOLUME_CLIMAX";
      return GS_HOLD;
     }

   // Filter arah besar H1: arah order wajib selaras dengan tren H1 (jangan lawan arus institusi)
   if(UseHTFTrendFilter)
     {
      if(!GSPositive(data.trend_close) || !GSPositive(data.trend_fast_ema) || !GSPositive(data.trend_slow_ema))
        { reason="HOLD_HTF_DATA_INVALID"; return GS_HOLD; }
      if(side==1 && (data.trend_close<data.trend_slow_ema || data.trend_fast_ema<data.trend_slow_ema))
        { reason="HOLD_HTF_TREND_BEARISH"; return GS_HOLD; }
      else if(side==-1 && (data.trend_close>data.trend_slow_ema || data.trend_fast_ema>data.trend_slow_ema))
        { reason="HOLD_HTF_TREND_BULLISH"; return GS_HOLD; }
     }

   // 2. CONFLUENCE SCORING SYSTEM (Sistem Pembobotan Multi-Aturan Fleksibel)
   if(UseConfluenceScoring)
     {
      int conf_score=0;

      // Pilar 1: Keselarasan Tren & Kemiringan Slope H1 (Maks 30 poin)
      if(UseHTFTrendFilter)
        {
         if((side==1 && data.trend_close>data.trend_slow_ema && data.trend_fast_ema>data.trend_slow_ema) ||
            (side==-1 && data.trend_close<data.trend_slow_ema && data.trend_fast_ema<data.trend_slow_ema))
            conf_score+=20;
         if(RequireHTFSlopeAlignment && GSPositive(data.previous_trend_fast_ema))
           {
            if((side==1 && data.trend_fast_ema>data.previous_trend_fast_ema) ||
               (side==-1 && data.trend_fast_ema<data.previous_trend_fast_ema))
               conf_score+=10;
           }
         else
            conf_score+=10;
        }

      // Pilar 2: Struktur EMA M15 & Model Setup (Maks 25 poin)
      if((side==1 && data.fast_ema>data.slow_ema) || (side==-1 && data.fast_ema<data.slow_ema))
         conf_score+=10;
      if(candidate_setup=="SETUP_PULLBACK")
         conf_score+=15;
      else if(candidate_setup=="SETUP_BREAKOUT")
         conf_score+=15;
      else
         conf_score+=10;

      // Pilar 3: Kekuatan Tren ADX (Maks 20 poin)
      if(UseADXFilter)
        {
         if(data.adx>=25.0) conf_score+=15;
         else if(data.adx>=ADXThreshold) conf_score+=10;
         if(RequireRisingADX && GSPositive(data.previous_adx) && data.adx>=data.previous_adx)
            conf_score+=5;
         else if(!RequireRisingADX)
            conf_score+=5;
        }

      // Pilar 4: Karakteristik Lilin M15 (Maks 20 poin)
      double crange=data.bar.high-data.bar.low;
      if((side==1 && data.bar.close>data.bar.open) || (side==-1 && data.bar.close<data.bar.open))
         conf_score+=10;
      if(crange>0.0 && MathAbs(data.bar.close-data.bar.open)/crange>=MinCandleBodyRatio)
         conf_score+=5;
      if(crange>0.0)
        {
         if(side==1 && (data.bar.close-data.bar.low)/crange>=MinCandleClosePercent/100.0)
            conf_score+=5;
         else if(side==-1 && (data.bar.high-data.bar.close)/crange>=MinCandleClosePercent/100.0)
            conf_score+=5;
        }

      // Pilar 5: Volume Transaksi Tick (Maks 15 poin)
      if(UseTickVolumeFilter && data.avg_tick_volume>0.0)
        {
         if((double)data.bar.tick_volume>=data.avg_tick_volume*1.0) conf_score+=15;
         else if((double)data.bar.tick_volume>=data.avg_tick_volume*MinTickVolumeRatio) conf_score+=10;
         else if((double)data.bar.tick_volume>=data.avg_tick_volume*0.50) conf_score+=5;
        }
      else
         conf_score+=15;

      // Pilar 6: Momentum RSI (Maks 10 poin)
      if(UseRSIMomentumThreshold)
        {
         if((side==1 && data.rsi>=50.0+RSIMomentumThreshold) ||
            (side==-1 && data.rsi<=50.0-RSIMomentumThreshold))
            conf_score+=10;
         else if(candidate_setup=="SETUP_PULLBACK")
            conf_score+=5;
        }
      else
         conf_score+=10;

      // Evaluasi Ambang Kelulusan Skor Konfluensi
      if(conf_score>=MinConfluenceScore)
        {
         reason=StringFormat("CANDIDATE_%s_CONF%d",candidate_setup,conf_score);
         return (GSSide)side;
        }
      else
        {
         reason=StringFormat("HOLD_CONFLUENCE_SCORE_LOW_%d_MIN%d",conf_score,MinConfluenceScore);
         return GS_HOLD;
        }
     }

   // 3. LEGACY STRICT GATES (Digunakan hanya jika UseConfluenceScoring dimatikan)
   if(UseRSIMomentumThreshold && RSIMomentumThreshold>0.0 && candidate_setup!="SETUP_PULLBACK")
     {
      if(side==1 && data.rsi<50.0+RSIMomentumThreshold)
        { reason="HOLD_RSI_MOMENTUM_WEAK"; return GS_HOLD; }
      else if(side==-1 && data.rsi>50.0-RSIMomentumThreshold)
        { reason="HOLD_RSI_MOMENTUM_WEAK"; return GS_HOLD; }
     }

   if(EMAPenetrationBufferATR>0.0 && GSPositive(data.atr) && candidate_setup=="SETUP_CROSSOVER")
     {
      double pen_buf=data.atr*EMAPenetrationBufferATR;
      if(side==1 && data.bar.close<data.fast_ema+pen_buf)
        { reason="HOLD_EMA_PENETRATION_INSUFFICIENT"; return GS_HOLD; }
      else if(side==-1 && data.bar.close>data.fast_ema-pen_buf)
        { reason="HOLD_EMA_PENETRATION_INSUFFICIENT"; return GS_HOLD; }
     }

   if(RequireFreshCross && candidate_setup=="SETUP_CROSSOVER")
     {
      bool fresh_buy=(data.previous_fast_ema<=data.previous_slow_ema && data.fast_ema>data.slow_ema) ||
                     (data.previous.close<=data.previous_fast_ema && data.bar.close>data.fast_ema);
      bool fresh_sell=(data.previous_fast_ema>=data.previous_slow_ema && data.fast_ema<data.slow_ema) ||
                      (data.previous.close>=data.previous_fast_ema && data.bar.close<data.fast_ema);
      if(side==1 && !fresh_buy)
        { reason="HOLD_NO_FRESH_TRIGGER"; return GS_HOLD; }
      if(side==-1 && !fresh_sell)
        { reason="HOLD_NO_FRESH_TRIGGER"; return GS_HOLD; }
     }

   if(UseHTFTrendFilter)
     {
      if(side==1)
        {
         if(RequireHTFSlopeAlignment && GSPositive(data.previous_trend_fast_ema) && data.trend_fast_ema<=data.previous_trend_fast_ema)
           { reason="HOLD_HTF_SLOPE_FLAT_OR_FALLING"; return GS_HOLD; }
        }
      else if(side==-1)
        {
         if(RequireHTFSlopeAlignment && GSPositive(data.previous_trend_fast_ema) && data.trend_fast_ema>=data.previous_trend_fast_ema)
           { reason="HOLD_HTF_SLOPE_FLAT_OR_RISING"; return GS_HOLD; }
        }
     }

   if(UseCandleDirectionFilter)
     {
      double range=data.bar.high-data.bar.low;
      if(side==1)
        {
         if(data.bar.close<=data.bar.open)
           { reason="HOLD_CANDLE_BEARISH"; return GS_HOLD; }
         if(range>0.0 && (data.bar.close-data.bar.low)/range<MinCandleClosePercent/100.0)
           { reason="HOLD_CANDLE_UPPER_WICK_REJECTION"; return GS_HOLD; }
        }
      else if(side==-1)
        {
         if(data.bar.close>=data.bar.open)
           { reason="HOLD_CANDLE_BULLISH"; return GS_HOLD; }
         if(range>0.0 && (data.bar.high-data.bar.close)/range<MinCandleClosePercent/100.0)
           { reason="HOLD_CANDLE_LOWER_WICK_REJECTION"; return GS_HOLD; }
        }
      if(UseCandleBodyFilter && MinCandleBodyRatio>0.0 && range>0.0)
        {
         double body=MathAbs(data.bar.close-data.bar.open);
         if(body/range<MinCandleBodyRatio)
           { reason="HOLD_CANDLE_BODY_TOO_SMALL"; return GS_HOLD; }
        }
     }

   if(UseTickVolumeFilter)
     {
      if(data.avg_tick_volume>0.0 && (double)data.bar.tick_volume<data.avg_tick_volume*MinTickVolumeRatio)
        { reason="HOLD_LOW_TICK_VOLUME"; return GS_HOLD; }
     }

   if(candidate_setup=="SETUP_PULLBACK")
      reason="CANDIDATE_PULLBACK";
   else if(candidate_setup=="SETUP_BREAKOUT")
      reason="CANDIDATE_BREAKOUT";
   else
      reason="CANDIDATE_CROSSOVER";

   return (GSSide)side;
  }
#endif
