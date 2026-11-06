"""Static safety/packaging checks. These cannot certify MQL compilation or broker behavior."""
from pathlib import Path
import hashlib
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ROOT / "mt5/Include"
SOURCES = sorted((ROOT / "mt5").rglob("*.mq?"))


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def without_comments(source):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)


class SourceContracts(unittest.TestCase):
    def test_spec_is_byte_identical_to_user_document(self):
        supplied = ROOT.parent / "GOLDSHIELD_AI_EA_V2_POWERFUL.md"
        actual = hashlib.sha256((ROOT / "SPEC.md").read_bytes()).hexdigest()
        self.assertEqual(actual, (ROOT / "SPEC.sha256").read_text().split()[0])
        if supplied.is_file():
            self.assertEqual(hashlib.sha256(supplied.read_bytes()).hexdigest(), actual)

    def test_custom_include_graph_is_complete(self):
        count = 0
        for path in SOURCES:
            for include in re.findall(r'^\s*#include\s+<([^>]+)>', path.read_text(encoding="utf-8"), re.M):
                if include.startswith("GoldShield/"):
                    self.assertTrue((INCLUDE / include).is_file(), f"{path}: missing {include}")
                    count += 1
                else:
                    self.assertEqual(include, "Trade/Trade.mqh", "Unexpected external dependency")
        self.assertGreater(count, 20)

    def test_default_flags_cannot_enable_trading(self):
        source = read("mt5/Include/GoldShield/Settings.mqh")
        self.assertRegex(source, r"ExecutionMode\s*=\s*SHADOW\s*;")
        for flag in ("EnableAutoTrading", "DemoTradingOptIn", "AllowRealTrading", "GridEnabled", "ApiEnabled", "TelegramEnabled"):
            self.assertRegex(source, rf"input bool {flag}=false;")

    def test_all_presets_disable_entries_and_optional_features(self):
        names = {name for name in re.findall(r"^input\s+\w+\s+(\w+)\s*=", read("mt5/Include/GoldShield/Settings.mqh"), re.M)}
        presets = list((ROOT / "mt5/Presets").glob("*.set"))
        self.assertGreaterEqual(len(presets), 2)
        for path in presets:
            data = dict(line.split("=", 1) for line in path.read_text().splitlines() if line and not line.startswith(";"))
            self.assertFalse(set(data) - names, f"Unknown preset fields: {path}")
            for flag in ("EnableAutoTrading", "DemoTradingOptIn", "AllowRealTrading", "GridEnabled", "ApiEnabled", "TelegramEnabled"):
                self.assertEqual(data.get(flag), "false", f"Unsafe preset {path}: {flag}")

    def test_real_and_unimplemented_modes_are_explicitly_refused(self):
        settings = read("mt5/Include/GoldShield/Settings.mqh")
        risk = read("mt5/Include/GoldShield/RiskFirewall.mqh")
        for code in ("MODE_NOT_IMPLEMENTED_PHASE1", "REAL_EXECUTION_UNAVAILABLE_PHASE1", "FEATURE_NOT_IMPLEMENTED_PHASE1"):
            self.assertIn(code, settings)
        self.assertIn("ACCOUNT_TRADE_MODE_DEMO", risk)
        self.assertIn("ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", risk)

    def test_only_executor_can_submit_trade_requests(self):
        calls = re.compile(r"\b(?:OrderSend|OrderSendAsync|PositionOpen|PositionClose|Buy|Sell|PositionModify)\s*\(")
        for path in SOURCES:
            if calls.search(without_comments(path.read_text(encoding="utf-8"))):
                self.assertEqual(path.name, "OrderExecutor.mqh", f"Unauthorized execution path {path}")
        executor = read("mt5/Include/GoldShield/OrderExecutor.mqh")
        self.assertEqual(executor.count("m_trade.PositionOpen("), 1)
        self.assertEqual(executor.count("m_trade.PositionClose("), 1)
        self.assertIn("m_trade.PositionClose(ticket,", executor)

    def test_order_intent_precedes_submission_and_is_not_auto_retried(self):
        executor = read("mt5/Include/GoldShield/OrderExecutor.mqh")
        start = executor.index("bool Open(")
        stop = executor.index("bool EmergencyClose(")
        entry = executor[start:stop]
        self.assertLess(entry.index("OrderCheck("), entry.index("store.BeginEntry("))
        self.assertLess(entry.index("store.BeginEntry("), entry.index("m_trade.PositionOpen("))
        self.assertLess(entry.index("log.Healthy()"), entry.index("m_trade.PositionOpen("))
        self.assertNotIn("ConfirmEntry(", entry)
        self.assertIn("GlobalVariablesFlush()", read("mt5/Include/GoldShield/Storage.mqh"))

    def test_no_http_dll_or_secondary_executor(self):
        for path in SOURCES:
            source = without_comments(path.read_text(encoding="utf-8"))
            self.assertNotRegex(source, r"\bWebRequest\s*\(")
            self.assertNotIn("#import", source)
        self.assertFalse((ROOT / "ai-service/app/main.py").exists())

    def test_features_read_only_closed_bars(self):
        source = read("mt5/Include/GoldShield/MarketData.mqh")
        self.assertRegex(source, r"CopyBuffer\(handle,0,1,1,buffer\)")
        self.assertRegex(source, r"CopyRates\(m_symbol,m_timeframe,1,2,rates\)")
        self.assertIn("snapshot.bar.time+PeriodSeconds(m_timeframe)", source)

    def test_timer_does_not_evaluate_new_signals(self):
        source = read("mt5/Experts/GoldShield_AI_V2.mq5")
        self.assertIn("void OnTimer(void) { GSProcess(false); }", source)
        self.assertIn("void OnTick(void) { GSProcess(true); }", source)
        self.assertIn("g_observed_bar=current; // History may finish", source)

    def test_callback_does_not_assume_fills_or_send_orders(self):
        callback = read("mt5/Experts/GoldShield_AI_V2.mq5").split("void OnTradeTransaction", 1)[1]
        self.assertNotIn("g_executor.", callback)
        self.assertNotIn("ConfirmEntry(", callback)
        self.assertIn("TRADE_TRANSACTION_REQUEST", callback)

    def test_account_exposure_is_not_filtered_by_ea_magic(self):
        source = read("mt5/Include/GoldShield/RiskFirewall.mqh")
        exposure = source.split("bool AccountExposure", 1)[1].split("bool BrokerSessionOpen", 1)[0]
        self.assertIn("PositionsTotal()", exposure)
        self.assertIn("OrderCalcProfit(", exposure)
        self.assertNotIn("POSITION_MAGIC", exposure)
        self.assertIn("ACCOUNT_POSITION_WITHOUT_KNOWN_STOP", exposure)
        self.assertIn("ACCOUNT_PENDING_ORDERS_BLOCK_ENTRY", exposure)

    def test_protection_and_fill_policy_are_explicit(self):
        risk = read("mt5/Include/GoldShield/RiskFirewall.mqh")
        executor = read("mt5/Include/GoldShield/OrderExecutor.mqh")
        for api in ("OrderCalcProfit(", "OrderCalcMargin(", "GSValidStops(", "GSRiskVolume("):
            self.assertIn(api, risk)
        self.assertIn("plan.sl,plan.tp,plan.comment", executor)
        self.assertIn("GSPreflightCodeOK(check.retcode)", executor)
        self.assertIn("SYMBOL_TRADE_EXECUTION_MARKET", read("mt5/Include/GoldShield/SymbolSpec.mqh"))

    def test_runtime_latch_survives_failed_persistence(self):
        source = read("mt5/Experts/GoldShield_AI_V2.mq5")
        self.assertIn("g_runtime_hard_block=true", source)
        self.assertIn('g_runtime_hard_block || g_storage.Get(".blocked")==2.0', source)
        self.assertIn("PERSISTENT_GLOBALS_MISSING_REVIEW_REQUIRED", read("mt5/Include/GoldShield/Storage.mqh"))

    def test_no_fake_compiled_binary_in_source_tree(self):
        self.assertFalse(list((ROOT / "mt5").rglob("*.ex5")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
