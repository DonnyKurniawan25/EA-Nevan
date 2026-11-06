"""Build an isolated DEMO-only 20-entry harness; preserve production and Cent files."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
MQL = Path(r"C:\Users\Nevan\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06\MQL5")


def main():
    policy = json.loads((ROOT / "reports/operating_policy.json").read_text())
    for name, digest in policy["protected_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    out = ROOT / "deployment/demo20"
    includes = out / "Include/GoldShieldDemo20"
    includes.mkdir(parents=True, exist_ok=True)
    for p in (ROOT / "mt5/Include/GoldShield").glob("*.mqh"):
        text = p.read_text().replace("<GoldShield/", "<GoldShieldDemo20/")
        if p.name == "OrderExecutor.mqh":
            text = text.replace("#include <GoldShieldDemo20/Metrics.mqh>", "#include <GoldShieldDemo20/Metrics.mqh>\n#include <GoldShieldDemo20/DemoTrial.mqh>")
            anchor = "      bool sent=m_trade.PositionOpen("
            assert text.count(anchor) == 1
            text = text.replace(anchor, "      if(!GSDemo20Reserve(store,reason)) return false;\n" + anchor)
        if p.name == "ChartUI.mqh":
            text = text.replace("#include <GoldShieldDemo20/Settings.mqh>", "#include <GoldShieldDemo20/Settings.mqh>\n#include <GoldShieldDemo20/DemoTrial.mqh>")
            text = text.replace('           "Aturan: ",', '           g_demo20_panel,"\\n",\n           "Aturan: ",')
        (includes / p.name).write_text(text, encoding="utf-8")
    shutil.copy2(out / "DemoTrial.mqh", includes / "DemoTrial.mqh")
    source = (ROOT / "mt5/Experts/GoldShield_AI_V2.mq5").read_text().replace("<GoldShield/", "<GoldShieldDemo20/")
    source = source.replace('#property version   "1.201"', '#property version   "1.220"')
    source = source.replace('   ZeroMemory(g_owned);', '   ZeroMemory(g_owned);\n   if(!MQLInfoInteger(MQL_TESTER))\n     {\n      for(int retry=0;retry<60;retry++)\n        {\n         if(TerminalInfoInteger(TERMINAL_CONNECTED) && AccountInfoDouble(ACCOUNT_EQUITY)>0.0) break;\n         Sleep(250);\n        }\n      if(!TerminalInfoInteger(TERMINAL_CONNECTED) || AccountInfoDouble(ACCOUNT_EQUITY)<=0.0)\n        { Print("DEMO20 account not synchronized; no state or orders created"); return INIT_FAILED; }\n     }')
    source = source.replace("   if(!GSValidateSettings(reason))", "   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO || ExecutionMode!=RULES_DEMO ||\n      AccountInfoString(ACCOUNT_SERVER)!=\"Exness-MT5Trial7\" || AccountInfoString(ACCOUNT_CURRENCY)!=\"USD\")\n     { Print(\"DEMO20 REFUSES NON-TARGET/REAL ACCOUNT\"); return INIT_FAILED; }\n   if(!GSValidateSettings(reason))")
    anchor = '   if(!g_log.Init(g_storage.Key()))'
    source = source.replace(anchor, '   if(!GSDemo20Init(g_storage,TradeSymbol,MagicNumber,reason)) { Print("DEMO20 INIT: ",reason); return INIT_FAILED; }\n' + anchor)
    anchor = '   if(TimeTradeServer()<g_storage.Get(".cooldown"))'
    source = source.replace(anchor, '   if(!GSDemo20CanEnter(g_storage,reason))\n     {\n      g_state.Set(PAUSED_MANUAL,reason,g_log);\n      GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());\n      g_processing=false; return;\n     }\n' + anchor)
    source = source.replace('GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());', 'GSDemo20Status(g_storage,g_owned,g_state); GSDrawPanel(g_state,g_owned,g_signal,g_storage.Key());')
    path = out / "GoldShield_DEMO20.mq5"
    path.write_text(source, encoding="utf-8")
    install = MQL / "Include/GoldShieldDemo20"
    install.mkdir(exist_ok=True)
    for p in includes.glob("*.mqh"):
        shutil.copy2(p, install / p.name)
    shutil.copy2(path, MQL / "Experts/GoldShield_DEMO20.mq5")
    # Signals, indicators and monetary risk math are exact namespace-only copies.
    for name in ("RuleSignal.mqh", "MarketData.mqh", "Settings.mqh", "SafetyMath.mqh", "RiskFirewall.mqh", "LossLimits.mqh"):
        assert (includes / name).read_text().replace("<GoldShieldDemo20/", "<GoldShield/") == (ROOT / "mt5/Include/GoldShield" / name).read_text()
    now = datetime.now(timezone(timedelta(hours=8)))
    existing = ROOT / "reports/demo20_session.json"
    plan = json.loads(existing.read_text()) if existing.exists() else {
        "created_at_wita": now.isoformat(), "magic": int(now.strftime("%y%m%d%H%M%S")) * 10 + 2,
        "user_authorization": "20 current-market DEMO trades using available virtual demo balance, maximum .01 lot; real Cent untouched",
        "status": "PREPARED_NOT_STARTED", "maximum_entry_submissions": 20, "account_mode": "DEMO_ONLY",
        "server": "Exness-MT5Trial7", "symbol": "XAUUSDm", "timeframe": "M15", "real_cent_used": False,
        "daily_entry_limit": 3, "daily_consecutive_loss_limit": 2,
        "note": "No forced signals. At most 3 entries/day, so 20 fills need at least 7 trading days; risk gates can stop sooner."}
    preset = (ROOT / "deployment/demo-tests/EXNESS_DEMO_BOUNDED.set").read_text()
    settings = dict(line.split("=", 1) for line in preset.splitlines() if line and not line.startswith(";"))
    settings.update(ExecutionMode="2", EnableAutoTrading="true", DemoTradingOptIn="true", AllowRealTrading="false",
                    MagicNumber=str(plan["magic"]), CapitalLimitUSD="0", RequiredAccountCurrency="USD")
    # Retain the existing bounded-demo risk preset, independent of the reserved Cent preset.
    preset = "; User-authorized, DEMO-only, 20-entry current-market trial.\n" + "\n".join(f"{k}={v}" for k,v in settings.items()) + "\n"
    (out / "DEMO20_CURRENT.set").write_text(preset, encoding="ascii")
    shutil.copy2(out / "DEMO20_CURRENT.set", MQL / "Presets/GoldShield/DEMO20_CURRENT.set")
    ini = "[Experts]\nEnabled=1\nAllowLiveTrading=1\n[StartUp]\nExpert=GoldShield_DEMO20\nExpertParameters=GoldShield\\DEMO20_CURRENT.set\nSymbol=XAUUSDm\nPeriod=M15\n"
    (out / "GoldShield_DEMO20.ini").write_text(ini, encoding="ascii")
    editor = Path(r"C:\Program Files\MetaTrader 5 EXNESS\MetaEditor64.exe")
    log = ROOT / "reports/compile/demo20.log"
    startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
    subprocess.run(f'"{editor}" /compile:"{MQL / "Experts/GoldShield_DEMO20.mq5"}" /inc:"{MQL}" /log:"{log}"', startupinfo=startup, timeout=120)
    raw = log.read_bytes(); text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe",b"\xfe\xff")) else "utf-16-le" if b"\0" in raw[:100] else "utf-8", errors="replace")
    print(next(line for line in text.splitlines() if "Result:" in line))
    if "0 errors, 0 warnings" not in text:
        print(text); raise RuntimeError("Demo-only harness compilation failed")
    plan["expert"] = "GoldShield_DEMO20"
    plan["compiled_binary_sha256"] = hashlib.sha256((MQL / "Experts/GoldShield_DEMO20.ex5").read_bytes()).hexdigest()
    plan["base_algorithm_sha256"] = policy["protected_sha256"]
    existing.write_text(json.dumps(plan, indent=2) + "\n")
    for name, digest in policy["protected_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    print("Compiled isolated DEMO20 harness. Original algorithm and Cent presets remain byte-identical.")


if __name__ == "__main__":
    main()
