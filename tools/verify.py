"""Run static contracts and optionally compile/execute shared math with MSVC."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def compilation_evidence():
    manifest = ROOT / "reports/mt5_compile.json"
    if not manifest.is_file():
        return "NOT_RUN", False
    evidence = json.loads(manifest.read_text(encoding="utf-8"))
    expected = {"GoldShield_AI_V2.mq5": ROOT / "mt5/Experts/GoldShield_AI_V2.mq5",
                "GoldShield_SafetyMath_Tests.mq5": ROOT / "mt5/Tests/GoldShield_SafetyMath_Tests.mq5"}
    targets = evidence.get("targets", [])
    current = evidence.get("status") == "PASS" and len(targets) == len(expected)
    for target in targets:
        source = expected.get(Path(target["source"]).name)
        binary = Path(target["binary"])
        current = current and bool(source and source.is_file() and binary.is_file())
        if current:
            current = (hashlib.sha256(source.read_bytes()).hexdigest() == target.get("source_sha256")
                       and hashlib.sha256(binary.read_bytes()).hexdigest() == target.get("binary_sha256")
                       and target.get("errors") == 0 and target.get("warnings") == 0)
    headers = evidence.get("header_sha256", {})
    current = current and len(headers) == len(list((ROOT / "mt5/Include/GoldShield").glob("*.mqh")))
    for relative, digest in headers.items():
        source = ROOT / relative
        current = current and source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == digest
    return ("PASS_0_ERRORS_0_WARNINGS" if current else "UNVERIFIED_OR_STALE_EVIDENCE"), current


def runtime_evidence(compiled):
    manifest = ROOT / "reports/mt5_runtime.json"
    if not compiled or not manifest.is_file():
        return "NOT_VERIFIED", "NOT_VERIFIED", "NOT_RUN"
    evidence = json.loads(manifest.read_text(encoding="utf-8"))
    unit = evidence.get("mt5_script_tests", {})
    receipt = Path(unit.get("receipt", "__missing__"))
    unit_ok = (unit.get("status") == "PASS" and unit.get("checks", 0) > 0
               and unit.get("failures") == 0 and receipt.is_file()
               and hashlib.sha256(receipt.read_bytes()).hexdigest() == unit.get("receipt_sha256")
               and hashlib.sha256((ROOT / "mt5/Tests/GoldShield_SafetyMath_Tests.mq5").read_bytes()).hexdigest() == unit.get("source_sha256")
               and hashlib.sha256((ROOT / "mt5/Include/GoldShield/SafetyMath.mqh").read_bytes()).hexdigest() == unit.get("math_sha256"))
    shadow = evidence.get("shadow_smoke", {})
    audit = Path(shadow.get("audit", "__missing__"))
    shadow_ok = (shadow.get("execution_mode") == "SHADOW"
                 and shadow.get("automatic_entry_enabled") is False
                 and shadow.get("positions_observed_in_trade_tab") == 0
                 and shadow.get("pending_orders_observed_in_trade_tab") == 0
                 and audit.is_file()
                 and hashlib.sha256(audit.read_bytes()).hexdigest() == shadow.get("audit_sha256")
                 and json.loads((ROOT / "reports/mt5_compile.json").read_text(encoding="utf-8"))["targets"][0].get("binary_sha256") == shadow.get("source_binary_sha256"))
    return (f"PASS_{unit['checks']}_CHECKS_ZERO_FAILURES" if unit_ok else "UNVERIFIED_OR_STALE_EVIDENCE",
            shadow.get("status", "NOT_VERIFIED") if shadow_ok else "UNVERIFIED_OR_STALE_EVIDENCE",
            evidence.get("strategy_tester", "NOT_RUN"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", action="store_true", help="Also run native C++ tests of the shared .mqh")
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native = {"status": "NOT_RUN", "assertions": 0}
    if args.native:
        run = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                              str(ROOT / "tools/Test-NativeMath.ps1")], cwd=ROOT, text=True, capture_output=True)
        print(run.stdout, end="")
        if run.stderr:
            print(run.stderr, file=sys.stderr, end="")
        match = re.search(r"PASS: (\d+) safety arithmetic assertions", run.stdout)
        native = {"status": "PASS" if run.returncode == 0 and match else "FAIL",
                  "assertions": int(match.group(1)) if match else 0,
                  "scope": "Actual SafetyMath.mqh with C++ math builtin adapters, not MetaEditor"}
    compile_status, compiled = compilation_evidence()
    unit_status, shadow_status, tester_status = runtime_evidence(compiled)
    runtime_path = ROOT / "reports/mt5_runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.is_file() else {}
    forward = runtime.get("demo_forward", {})
    receipt = Path(forward.get("audit", "__missing__"))
    forward_ok = (compiled and forward.get("fill_confirmed_in_broker_snapshot") is True
                  and forward.get("server_stop_loss", 0) > 0
                  and forward.get("server_take_profit", 0) > 0
                  and receipt.is_file()
                  and hashlib.sha256(receipt.read_bytes()).hexdigest() == forward.get("audit_sha256")
                  and json.loads((ROOT / "reports/mt5_compile.json").read_text(encoding="utf-8"))["targets"][0].get("binary_sha256") == forward.get("ea_binary_sha256"))
    report = {
        "checked_at_wita": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "phase": 1,
        "static_contracts": {"run": result.testsRun, "failures": len(result.failures),
                             "errors": len(result.errors), "status": "PASS" if result.wasSuccessful() else "FAIL"},
        "shared_math_native": native,
        "mql5_compile": compile_status,
        "mt5_script_tests": unit_status,
        "mt5_shadow_smoke": shadow_status,
        "strategy_tester": tester_status,
        "broker_integration": ("FIRST_DEMO_FILL_AND_SERVER_STOPS_OBSERVED_FULL_SAFETY_PENDING" if forward_ok else
                               "CURRENT_BUILD_DEMO_QUOTES_VERIFIED_FORWARD_EXECUTION_NOT_TESTED" if shadow_status.startswith("PASS") else "NOT_RUN"),
        "phase1_acceptance": "G0_UNIT_AND_BASIC_SHADOW_VERIFIED_FULL_SAFETY_ACCEPTANCE_PENDING" if compiled and unit_status.startswith("PASS") and shadow_status.startswith("PASS") else "ACCEPTANCE_PENDING",
        "phase2": "NOT_STARTED_GATE_PENDING",
        "trading_orders_submitted_by_development_tools": 0,
        "user_authorized_demo_robot_entry_requests": forward.get("user_authorized_robot_entry_requests", 0) if forward_ok else "UNVERIFIED",
        "demo_backtest": runtime.get("rules_demo_backtest", "NOT_RUN"),
        "improvement_comparison": runtime.get("improvement_comparison", "NOT_RUN"),
        "small_capital": runtime.get("small_capital", "NOT_RUN"),
    }
    output = ROOT / "reports/verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {output}")
    return 0 if result.wasSuccessful() and native["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
