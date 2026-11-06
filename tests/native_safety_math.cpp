// Executes the actual shared .mqh arithmetic, with C++ equivalents of MQL math builtins.
// This is not a substitute for MetaEditor or MT5 execution.
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <random>
using uint = unsigned int;
bool MathIsValidNumber(double x) { return std::isfinite(x); }
double MathMin(double a, double b) { return std::min(a, b); }
double MathMax(double a, double b) { return std::max(a, b); }
double MathFloor(double x) { return std::floor(x); }
double MathCeil(double x) { return std::ceil(x); }
double MathAbs(double x) { return std::abs(x); }
double NormalizeDouble(double x, int digits) {
    const double scale = std::pow(10.0, digits);
    return std::round(x * scale) / scale;
}
#include "../mt5/Include/GoldShield/SafetyMath.mqh"

int assertions = 0;
void require(bool condition, const char* name) {
    ++assertions;
    if (!condition) { std::cerr << "FAIL: " << name << '\n'; std::exit(1); }
}
bool near(double a, double b) { return std::abs(a - b) < 1e-8; }
int main() {
    require(near(GSVolumeDown(0.025, 0.01, 100, 0.01), 0.02), "round down lots");
    require(GSVolumeDown(0.009, 0.01, 100, 0.01) == 0, "minimum lot rejection");
    require(near(GSVolumeDown(0.7, 0.25, 100, 0.25), 0.5), "non-decimal lot step");
    require(near(GSVolumeDown(200, 0.01, 1.23, 0.01), 1.23), "broker maximum");
    require(GSVolumeDown(-1, 0.01, 100, 0.01) == 0, "negative lots");
    require(GSVolumeDown(1, 0.01, 100, 0) == 0, "zero step");
    require(GSVolumeDown(std::numeric_limits<double>::infinity(), 0.01, 100, 0.01) == 0, "infinite volume");
    require(GSVolumeDown(std::numeric_limits<double>::quiet_NaN(), 0.01, 100, 0.01) == 0, "NaN volume");
    require(near(GSTickDown(2700.129, 0.05, 2), 2700.10), "buy SL tick floor");
    require(near(GSTickUp(2700.129, 0.05, 2), 2700.15), "sell SL tick ceil");
    require(near(GSTickDown(2700.1239, 0.001, 3), 2700.123), "three digit symbol");
    require(near(GSRiskVolume(100, 500, 25, 10, 10, 0.01, 100, 0.01), 0.15), "buffered risk sizing");
    require(GSRiskVolume(1, 500, 25, 10, 10, 0.01, 100, 0.01) == 0, "budget below min lot");
    require(near(GSRiskVolume(10000, 500, 25, 10, 0.01, 0.01, 100, 0.01), 0.01), "base lot ceiling");
    require(GSRiskVolume(100, 500, -1, 10, 10, 0.01, 100, 0.01) == 0, "invalid cost buffer");
    require(GSValidStops(true, 2700.2, 2700, 2700.2, 2690, 2720.6, 0.5), "valid BUY protection");
    require(GSValidStops(false, 2700, 2700, 2700.2, 2710, 2680, 0.5), "valid SELL protection");
    require(!GSValidStops(true, 2700.2, 2700, 2700.2, 2700.1, 2720, 0.5), "buy stop must be below bid");
    require(!GSValidStops(false, 2700, 2700, 2700.2, 2700.1, 2680, 0.5), "sell stop must be above ask");
    require(!GSValidStops(true, 2700.2, 2700, 2700.2, 2690, 2699, 0.5), "wrong target side");
    require(!GSValidStops(true, 2700.2, 2700, 2700.2, 0, 2720, 0.5), "missing server stop");
    require(!GSValidStops(true, 2700.2, 2701, 2700.2, 2690, 2720, 0.5), "inverted spread");
    require(GSValidOHLC(2700, 2702, 2698, 2701), "valid OHLC");
    require(!GSValidOHLC(2700, 2699, 2698, 2701), "invalid high");
    require(!GSValidOHLC(2700, 2702, 2700.5, 2701), "invalid low");
    require(GSBaselineSide(2710, 2705, 2700, 55, true) == 1, "BUY baseline");
    require(GSBaselineSide(2690, 2695, 2700, 45, true) == -1, "SELL baseline");
    require(GSBaselineSide(2710, 2705, 2700, 80, true) == 0, "RSI veto");
    require(GSBaselineSide(2710, 2705, 2700, 80, false) == 1, "optional RSI");
    require(GSBaselineSide(2700, 2700, 2700, 50, true) == 0, "uncertain HOLD");
    require(GSPreflightCodeOK(0) && GSPreflightCodeOK(10009), "OrderCheck success code differs from send");
    require(!GSPreflightCodeOK(10019) && !GSPreflightCodeOK(10027), "broker preflight rejections");
    require(GSTrendPullbackOK(1,105,108,107,102,103,105,100,99,120,115,110,5,1), "confirmed BUY pullback");
    require(GSTrendPullbackOK(-1,95,92,98,93,97,95,100,101,80,85,90,5,1), "confirmed SELL pullback");
    require(!GSTrendPullbackOK(1,105,108,107,102,103,105,100,99,105,110,115,5,1), "counter H1 trend veto");
    require(!GSTrendPullbackOK(1,105,108,109,102,103,105,100,99,120,115,110,5,1), "unbroken prior high veto");
    require(!GSTrendPullbackOK(1,105,108,107,104,103,105,100,99,120,115,110,5,1), "no pullback veto");
    require(!GSTrendPullbackOK(1,105,108,107,102,103,105,100,99,120,115,110,2,1), "extended entry veto");
    require(!GSTrendPullbackOK(1,105,108,107,102,103,105,100,101,120,115,110,5,1), "falling slow EMA veto");
    require(near(GSLossAllowance(100000,99990,99.9,.03,.075,-16,-16),14), "loss reduces next entry allowance");
    require(near(GSLossAllowance(100000,100020,99.9,.03,.075,20,20),30), "profits do not enlarge daily cap");
    require(near(GSLossAllowance(100000,99905,99.9,.03,.075,0,-60),5), "remaining shield limits entry");
    require(GSLossAllowance(100000,99900,99.9,.03,.075,0,0)==0, "shield floor has no headroom");
    require(GSLossAllowance(100000,100000,99.9,.03,.075,-31,-31)==0, "daily exhaustion rejects");
    require(GSLossAllowance(100000,100000,99.9,.03,.075,0,-76)==0, "weekly exhaustion rejects");
    require(GSLossAllowance(100000,100000,99.9,.03,.075,std::numeric_limits<double>::quiet_NaN(),0)==0, "nonfinite history rejects");
    require(near(GSCapitalLedgerEquity(10,100000,99999),9), "virtual capital tracks account loss");
    require(near(GSCapitalLedgerEquity(10,100000,110000),10), "profit or deposit cannot raise the capital cap");
    require(near(GSCapitalLedgerEquity(10,100000,99980),-10), "virtual budget cannot refill itself");
    require(GSCapitalLedgerEquity(0,100000,99999)<0, "invalid virtual capital rejects");
    require(!GSCapitalMarginOK(10,0,20,50,500), "standard gold margin exceeds ten dollar budget");
    require(GSCapitalMarginOK(10,0,1,50,500), "small affordable margin accepted");
    require(GSCapitalMarginOK(10,1,1,50,500), "existing margin is reserved");
    require(!GSCapitalMarginOK(10,1,1.01,50,500), "virtual margin level threshold enforced");
    require(!GSCapitalMarginOK(10,0,-1,50,500), "negative margin rejected");

    std::mt19937 generator(20261106);
    std::uniform_real_distribution<double> budgets(0.001, 10000);
    std::uniform_real_distribution<double> losses(1, 100000);
    const double steps[] = {0.001, 0.01, 0.1, 0.25};
    for (int i = 0; i < 10000; ++i) {
        const double budget = budgets(generator), loss = losses(generator);
        const double step = steps[i % 4];
        const double cap = static_cast<double>((i % 100) + 1) * step;
        const double volume = GSRiskVolume(budget, loss, 25, 10, cap, step, 100, step);
        require(std::isfinite(volume) && volume >= 0, "finite nonnegative result");
        require(volume <= cap + 1e-9, "never exceed requested volume");
        require(volume * (loss * 1.25 + 10) <= budget + 1e-7, "never exceed buffered budget");
        require(near(volume / step, std::round(volume / step)), "volume follows broker step");
    }
    std::cout << "PASS: " << assertions << " safety arithmetic assertions (actual .mqh; C++ builtin shim)\n";
}
