#ifndef GOLDSHIELD_SAFETY_MATH_MQH
#define GOLDSHIELD_SAFETY_MATH_MQH

bool GSPositive(const double value)
  {
   return MathIsValidNumber(value) && value>0.0;
  }
bool GSPreflightCodeOK(const uint code)
  {
   // Official OrderCheck examples return 0 on success; OrderSend uses 10009 (DONE).
   return code==0 || code==10009;
  }
double GSVolumeDown(const double requested,const double minimum,
                    const double maximum,const double step)
  {
   if(!GSPositive(requested) || !GSPositive(minimum) ||
      !GSPositive(maximum) || !GSPositive(step) || maximum<minimum)
      return 0.0;
   double cap=MathMin(requested,maximum);
   double result=NormalizeDouble(MathFloor(cap/step+1e-10)*step,8);
   if(!GSPositive(result) || result>cap+1e-9 || result<minimum-1e-9)
      return 0.0;
   return result;
  }
double GSTickDown(const double price,const double tick_size,const int digits)
  {
   if(!GSPositive(price) || !GSPositive(tick_size)) return 0.0;
   return NormalizeDouble(MathFloor(price/tick_size+1e-10)*tick_size,digits);
  }
double GSTickUp(const double price,const double tick_size,const int digits)
  {
   if(!GSPositive(price) || !GSPositive(tick_size)) return 0.0;
   return NormalizeDouble(MathCeil(price/tick_size-1e-10)*tick_size,digits);
  }
double GSRiskVolume(const double budget,const double loss_per_lot,
                    const double buffer_pct,const double cost_per_lot,
                    const double cap,const double minimum,
                    const double maximum,const double step)
  {
   if(!GSPositive(budget) || !GSPositive(loss_per_lot) ||
      !MathIsValidNumber(buffer_pct) || buffer_pct<0.0 ||
      !MathIsValidNumber(cost_per_lot) || cost_per_lot<0.0 || !GSPositive(cap))
      return 0.0;
   double cost=loss_per_lot*(1.0+buffer_pct/100.0)+cost_per_lot;
   if(!GSPositive(cost)) return 0.0;
   return GSVolumeDown(MathMin(cap,budget/cost),minimum,maximum,step);
  }
bool GSValidOHLC(const double open,const double high,const double low,const double close)
  {
   return GSPositive(open) && GSPositive(high) && GSPositive(low) &&
          GSPositive(close) && high>=MathMax(open,close) &&
          low<=MathMin(open,close) && high>=low;
  }
bool GSValidStops(const bool buy,const double entry,const double bid,const double ask,
                  const double sl,const double tp,const double minimum_distance)
  {
   if(!GSPositive(entry) || !GSPositive(bid) || !GSPositive(ask) || ask<bid ||
      !GSPositive(sl) || !GSPositive(tp) || !MathIsValidNumber(minimum_distance) ||
      minimum_distance<0.0) return false;
   if(buy) return sl<entry && tp>entry && bid-sl>=minimum_distance &&
                  tp-bid>=minimum_distance;
   return sl>entry && tp<entry && sl-ask>=minimum_distance &&
          ask-tp>=minimum_distance;
  }
int GSBaselineSide(const double close,const double fast,const double slow,
                   const double rsi,const bool use_rsi)
  {
   if(!GSPositive(close) || !GSPositive(fast) || !GSPositive(slow) ||
      !MathIsValidNumber(rsi) || rsi<0.0 || rsi>100.0) return 0;
   if(fast>slow && close>fast && (!use_rsi || (rsi>=50.0 && rsi<=70.0))) return 1;
   if(fast<slow && close<fast && (!use_rsi || (rsi>=30.0 && rsi<=50.0))) return -1;
   return 0;
  }

bool GSTrendPullbackOK(const int side,const double open,const double close,
                      const double previous_high,const double previous_low,
                      const double previous_fast,const double fast,const double slow,
                      const double previous_slow,const double trend_close,
                      const double trend_fast,const double trend_slow,
                      const double atr,const double stretch)
  {
   if(!GSPositive(open) || !GSPositive(close) || !GSPositive(previous_high) ||
      !GSPositive(previous_low) || previous_high<previous_low || !GSPositive(previous_fast) ||
      !GSPositive(fast) || !GSPositive(slow) || !GSPositive(previous_slow) ||
      !GSPositive(trend_close) || !GSPositive(trend_fast) || !GSPositive(trend_slow) ||
      !GSPositive(atr) || !GSPositive(stretch) || MathAbs(close-fast)>atr*stretch) return false;
   if(side==1)
      return trend_close>trend_fast && trend_fast>trend_slow && fast>previous_fast &&
             slow>=previous_slow && previous_low<=previous_fast && close>previous_high && close>open;
   if(side==-1)
      return trend_close<trend_fast && trend_fast<trend_slow && fast<previous_fast &&
             slow<=previous_slow && previous_high>=previous_fast && close<previous_low && close<open;
   return false;
  }

double GSLossAllowance(const double reference,const double equity,const double floor_pct,
                       const double daily_pct,const double weekly_pct,
                       const double daily_net,const double weekly_net)
  {
   if(!GSPositive(reference) || !GSPositive(equity) || !GSPositive(floor_pct) || floor_pct>=100.0 ||
      !GSPositive(daily_pct) || !GSPositive(weekly_pct) ||
      !MathIsValidNumber(daily_net) || !MathIsValidNumber(weekly_net)) return 0.0;
   double daily=reference*daily_pct/100.0+MathMin(0.0,daily_net);
   double weekly=reference*weekly_pct/100.0+MathMin(0.0,weekly_net);
   double total=equity-reference*floor_pct/100.0;
   // Gains do not enlarge daily/weekly budgets. Existing losses reduce available risk.
   return MathMax(0.0,MathMin(total,MathMin(daily,weekly)));
  }
double GSCapitalLedgerEquity(const double capital,const double anchor,const double actual)
  {
   if(!GSPositive(capital) || !GSPositive(anchor) || !GSPositive(actual)) return -1.0;
   // Profit/deposits never raise the allocated budget above the initial cap.
   return MathMin(capital,capital+(actual-anchor));
  }
bool GSCapitalMarginOK(const double equity,const double used,const double proposed,
                       const double free_pct,const double margin_level_pct)
  {
   if(!GSPositive(equity) || !MathIsValidNumber(used) || used<0.0 ||
      !MathIsValidNumber(proposed) || proposed<0.0 || !GSPositive(free_pct) ||
      free_pct>100.0 || !GSPositive(margin_level_pct)) return false;
   double total=used+proposed;
   return equity-total>=equity*free_pct/100.0 &&
          (total==0.0 || equity/total*100.0>=margin_level_pct);
  }
#endif
