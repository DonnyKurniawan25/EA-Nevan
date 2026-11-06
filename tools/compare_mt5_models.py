"""Run the predeclared model comparison in MT5. Live chart stays SHADOW."""
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from analyze_mt5_test import analyze, read_text

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = Path(r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe")
DATA = Path(r"C:\Users\Nevan\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06")
AGENT = Path(r"C:\Users\Nevan\AppData\Roaming\MetaQuotes\Tester\53785E099C927DB68A545C249CDBCE06\Agent-127.0.0.1-3000")


def risk_checks(deals_path, audit_path):
    deals = list(csv.DictReader(deals_path.open(encoding="utf-8-sig")))
    audit = list(csv.DictReader(audit_path.open(encoding="utf-8-sig")))
    entries = {}
    for row in deals:
        if int(row["entry"]) == 0:
            entries.setdefault(row["position_id"], row["time_server"][:10])
    per_day = {}
    for day in entries.values():
        per_day[day] = per_day.get(day, 0) + 1
    intent_checks = []
    remaining_checks = []
    streak_checks = []
    positions = {}
    for deal in deals:
        item = positions.setdefault(deal["position_id"], {"net": 0, "close": ""})
        item["net"] += sum(float(deal[k]) for k in ("profit", "commission", "swap", "fee"))
        if int(deal["entry"]) in (1, 3):
            item["close"] = max(item["close"], deal["time_server"])
    for event in audit:
        if event["event"] != "ORDER_INTENT":
            continue
        values = dict(re.findall(r"(lots|budget|risk_est)=([\d.]+)", event["details"]))
        intent_checks.append(float(values["lots"]) <= .01 + 1e-9
                             and float(values["risk_est"]) <= float(values["budget"]) + .011
                             and float(values["budget"]) <= 30.011)
        when = datetime.strptime(event["server_time"], "%Y.%m.%d %H:%M:%S")
        day = when.replace(hour=0, minute=0, second=0)
        week = day - timedelta(days=day.weekday())
        before = [d for d in deals if d["time_server"] < event["server_time"]]
        def net_since(start):
            return sum(sum(float(d[k]) for k in ("profit", "commission", "swap", "fee"))
                       for d in before if d["time_server"] >= start.strftime("%Y.%m.%d %H:%M:%S"))
        equity = 100000 + net_since(datetime.min)
        allowance = max(0, min(30 + min(0, net_since(day)), 75 + min(0, net_since(week)), equity - 99900))
        remaining_checks.append(float(values["budget"]) <= allowance + .011)
        closed = sorted((p for p in positions.values() if day.strftime("%Y.%m.%d %H:%M:%S") <= p["close"] < event["server_time"]),
                        key=lambda p: p["close"], reverse=True)
        streak = 0
        for position in closed:
            if position["net"] >= -1e-8:
                break
            streak += 1
        streak_checks.append(streak < 2)
    htf_checks = []
    for event in audit:
        if event["event"] == "SIGNAL" and event["reason_code"] == "CANDIDATE_CONFIRMED_TREND_PULLBACK":
            close_time = int(event["candle_id_server"]) + 900
            htf = int(re.search(r"htf_available=(\d+)", event["details"])[1])
            htf_checks.append(0 <= close_time - htf < 3600)
    return {"unique_entries_per_day_at_most_3": max(per_day.values(), default=0) <= 3,
            "buffered_entry_risk_within_remaining_budget": all(intent_checks),
            "entry_budget_within_independent_daily_weekly_shield_headroom": all(remaining_checks),
            "no_entry_after_two_daily_losses": all(streak_checks),
            "confirmed_signals_use_closed_fresh_h1": all(htf_checks),
            "intent_count_matches_positions": len(intent_checks) == len(entries),
            "confirmed_signal_count": len(htf_checks)}


def main():
    active = subprocess.run(["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/FO", "CSV", "/NH"],
                            text=True, capture_output=True)
    if '"terminal64.exe"' in active.stdout.lower():
        raise RuntimeError("Close MT5 first; do not reconfigure an existing live terminal")
    plan = json.loads((ROOT / "reports/improvement_test_plan.json").read_text())
    stamp = datetime.now().strftime("%y%m%d%H%M%S")
    results = []
    for index, window in enumerate(plan["windows"]):
        for model in (0, 1):
            label = f'{window["from"][:7].replace(".", "-")}_{"baseline" if model == 0 else "confirmed"}'
            receipt = ROOT / "reports/runtime/improvements" / label
            receipt.mkdir(parents=True, exist_ok=True)
            magic = int(stamp) * 10 + index * 2 + model
            name = f"GOLDSHIELD_COMPARE_{magic}.set"
            preset = (ROOT / "deployment/demo-tests/EXNESS_DEMO_BOUNDED.set").read_text()
            preset = preset.replace("MagicNumber=26011060", f"MagicNumber={magic}")
            # The PC's forward preset may be parked OFF after an unfavorable test.
            # Opt-in is forced only in this historical tester copy; live chart is SHADOW.
            preset = re.sub(r"^ExecutionMode=.*$", "ExecutionMode=2", preset, flags=re.M)
            preset = re.sub(r"^EnableAutoTrading=.*$", "EnableAutoTrading=true", preset, flags=re.M)
            preset = re.sub(r"^DemoTradingOptIn=.*$", "DemoTradingOptIn=true", preset, flags=re.M)
            preset = re.sub(r"^(SignalModel|TrendTimeframe|MaxEntryStretchATR|MaxDailyLossPct|MaxWeeklyLossPct|MaxConsecutiveLossesPerDay|MaxEntriesPerDay)=.*\n?", "", preset, flags=re.M)
            preset += (f"\nSignalModel={model}\nTrendTimeframe=16385\nMaxEntryStretchATR=1.0\n"
                       "MaxDailyLossPct=0.03\nMaxWeeklyLossPct=0.075\n"
                       "MaxConsecutiveLossesPerDay=2\nMaxEntriesPerDay=3\n")
            (DATA / "MQL5/Profiles/Tester" / name).write_text(preset, encoding="ascii")
            (receipt / "inputs.set").write_text(preset, encoding="ascii")
            config = (ROOT / "deployment/demo-tests/GoldShield_BACKTEST.ini").read_text()
            config = re.sub(r"ExpertParameters=GOLDSHIELD_RULES_TEST_.*?\.set", f"ExpertParameters={name}", config)
            config = re.sub(r"FromDate=.*", f'FromDate={window["from"]}', config)
            config = re.sub(r"ToDate=.*", f'ToDate={window["to_exclusive"]}', config)
            config = config.replace("ShutdownTerminal=0", "ShutdownTerminal=1")
            # Native custom receipts below avoid absolute-path report limitations.
            ini = receipt / "tester.ini"
            ini.write_text(config, encoding="ascii")
            print(f"START {label} magic={magic}", flush=True)
            started = time.monotonic()
            process = subprocess.Popen(f'"{TERMINAL}" /config:"{ini}"')
            while process.poll() is None:
                if time.monotonic() - started > 900:
                    raise TimeoutError(f"{label}: MT5 still running; inspect it before continuing")
                time.sleep(.5)
            files = list((AGENT / "MQL5/Files/GoldShield").glob(f"test_{magic}_*.json"))
            if len(files) != 1:
                raise RuntimeError(f"{label}: expected one completed tester receipt, found {len(files)}")
            native_source = files[0]
            deals_source = native_source.with_name(native_source.stem + "_deals.csv")
            native = receipt / native_source.name
            deals = receipt / deals_source.name
            shutil.copy2(native_source, native)
            shutil.copy2(deals_source, deals)
            audits = list((AGENT / "MQL5/Files/GoldShield").glob("GS2.*.csv"))
            if len(audits) != 1:
                raise RuntimeError(f"{label}: ambiguous audit")
            audit = receipt / "audit.csv"
            shutil.copy2(audits[0], audit)
            result = analyze(native, deals)
            result.update(label=label, signal_model=model, window=window,
                          risk_checks=risk_checks(deals, audit),
                          wall_seconds=round(time.monotonic() - started, 2))
            if not result["reconciled"] or not all(v for k, v in result["risk_checks"].items() if k != "confirmed_signal_count"):
                raise RuntimeError(f"{label}: reconciliation or risk evidence failed")
            (receipt / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
            log = AGENT / "logs" / datetime.now().strftime("%Y%m%d.log")
            with log.open("rb") as f:
                f.seek(max(0, log.stat().st_size - 10000))
                tail = f.read().decode("utf-16-le", errors="replace")
            summary = [line for line in tail.splitlines()
                       if any(s in line for s in ("GOLDSHIELD_TEST_RESULT", "final balance", "bars generated", "Test passed"))]
            (receipt / "tester_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
            results.append(result)
            (ROOT / "reports/improvement_comparison.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps({k: result[k] for k in ("label", "closed_positions", "wins_after_all_costs",
                  "win_rate_after_costs_pct", "net_profit_after_all_costs", "maximum_equity_drawdown_pct_native", "risk_checks")}), flush=True)
    print("COMPLETE: all predeclared comparisons reconciled", flush=True)


if __name__ == "__main__":
    main()
