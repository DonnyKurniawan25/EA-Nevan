"""Real MT5-shaped CSV fixtures; no network or trading terminal required."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("telegram_notifier", ROOT / "tools/telegram_notifier.py")

AUDIT = "event_id,server_time,utc_time,clock_source,event,symbol,candle_id_server,reason_code,details\r\n"
SNAPSHOT = "time_server,account_mode,symbol,limit,entry_submissions,filled_positions,closed_positions,wins,losses,net_closed,currency,open_positions,trial_status,core_state,core_reason\r\n"


def audit(event="ORDER_RESULT", details="method=true retcode=10009 order=12 deal=13 filled_volume=0.01", reason="RECONCILIATION_REQUIRED", event_id="1234-1", symbol="XAUUSD"):
    out = io.StringIO(newline="")
    csv.writer(out).writerow([event_id, "2026.11.06 12:00:00", "2026.11.06 10:00:00", "BROKER_SERVER_AND_PC_UTC", event, symbol, "123", reason, details])
    return out.getvalue().encode("cp1252")


class NotifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "GoldShield"
        self.source.mkdir()
        self.state = self.base / "state"
        self.file = self.source / "GS2.0123456789ABCDEF.csv"
        self.file.write_bytes(AUDIT.encode() + audit(event_id="historical"))
        self.sent = []
        self.n = None
        self.snapshot()

    def notifier(self, sender=None, **kwargs):
        module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(module)
        self.module = module
        self.n = module.Notifier(self.source, self.state, sender or self.sent.append, **kwargs)
        return self.n

    def append(self, row):
        with self.file.open("ab") as handle:
            handle.write(row)

    def test_first_run_baselines_then_reports_entry_request_not_fill(self):
        n = self.notifier()
        n.poll()
        self.assertEqual(self.sent, [])
        self.append(audit())
        n.poll()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Permintaan entry", self.sent[0])
        self.assertIn("BUKAN konfirmasi posisi", self.sent[0])
        self.assertNotIn("filled_volume", self.sent[0])
        self.notifier().poll()
        self.assertEqual(len(self.sent), 1)

    def test_timeout_retries_durable_pending_after_restart_and_rotation(self):
        n = self.notifier()
        n.poll()
        self.append(audit())
        def fail(message):
            raise TimeoutError("fake network timeout")
        n.sender = fail
        with self.assertRaises(TimeoutError):
            n.poll()
        stored = json.loads((self.state / "cursor.json").read_text())
        self.assertIsNotNone(stored["pending"])
        self.assertIn("Permintaan entry — BUKAN konfirmasi posisi", stored["pending"]["message"])
        self.file.unlink()
        self.notifier().poll()
        self.assertEqual(len(self.sent), 1)
        self.notifier().poll()
        self.assertEqual(len(self.sent), 1)

    def test_complete_rows_only_and_offsets_survive_rename_truncate(self):
        n = self.notifier()
        n.poll()
        first, second = audit(event_id="new-1"), audit(event_id="new-2")
        self.append(first + second[:-5])
        n.poll()
        self.assertEqual(len(self.sent), 1)
        self.append(second[-5:] + audit(event_id="new-3"))
        n.poll()
        self.assertEqual(len(self.sent), 3)
        cursor = next(iter(n.state["audit"].values()))
        self.assertEqual(cursor["offset"] if isinstance(cursor, dict) else cursor, self.file.stat().st_size)
        rotated = self.file.with_name(self.file.name + ".1")
        self.file.rename(rotated)
        self.file.write_bytes(AUDIT.encode() + audit(event_id="new-4"))
        n.poll()
        self.assertEqual(len(self.sent), 4)
        self.file.write_bytes(AUDIT.encode() + audit(event_id="new-5"))
        n.poll()
        self.assertEqual(len(self.sent), 5)

    def test_meaningful_events_are_plain_whitelisted_and_hold_is_silent(self):
        n = self.notifier()
        n.poll()
        for event in ("SIGNAL", "STATE", "ORDER_INTENT", "ORDER_CHECK", "FILL_CONFIRMED", "CLOSE_RESULT", "EXIT_CONFIRMED", "POSITION_CLOSED", "STORAGE_ERROR"):
            details = "READY -> PAUSED_RISK" if event == "STATE" else "lots=0.01 retcode=10009 password=secret login=123456 token=123:ABC <b>hack</b>"
            self.append(audit(event=event, details=details, reason="EQUITY_REFERENCE_FLOOR"))
        self.append(audit(event="STATE", details="READY -> PAUSED_RISK", reason="EQUITY_REFERENCE_FLOOR"))
        self.append(audit(event="STATE", details="SIGNAL_PENDING -> READY", reason="HOLD_SPREAD_LIMIT"))
        n.poll()
        self.assertEqual(len(self.sent), 8)
        text = "\n".join(self.sent)
        self.assertIn("Posisi terkonfirmasi", text)
        self.assertIn("Permintaan tutup", text)
        self.assertIn("PAUSED_RISK", text)
        for forbidden in ("secret", "123456", "123:ABC", "hack", "HOLD_SPREAD", "<b>"):
            self.assertNotIn(forbidden, text)
        self.append(audit(event="ORDER_INTENT", details="lots=0.02 " + "x" * 10000, reason="PASSWORD_SECRET"))
        n.poll()
        self.assertNotIn("PASSWORD_SECRET", self.sent[-1])
        self.assertLessEqual(len(self.sent[-1]), 1500)

    def snapshot(self, filled=0, closed=0, net="0", opened=0, **overrides):
        fields = ["2026.11.06 12:00:00", "DEMO", "XAUUSD", "20", str(filled), str(filled), str(closed), str(closed), "0", net, "USD", str(opened), "RUNNING_WAIT_VALID_SIGNAL", "READY", "WAIT_NEXT_CLOSED_BAR"]
        for name, value in overrides.items():
            fields[SNAPSHOT.strip().split(",").index(name)] = str(value)
        out = io.StringIO(newline="")
        csv.writer(out).writerow(fields)
        path = self.source / "demo20_2026001.csv"
        path.write_bytes(SNAPSHOT.encode() + out.getvalue().encode("cp1252"))
        return path

    def test_snapshot_rewrite_reports_confirmed_counts_and_only_aggregate_net(self):
        path = self.snapshot(filled=1, opened=1)
        n = self.notifier()
        n.poll()
        self.assertEqual(self.sent, [])
        self.snapshot(filled=3, closed=2, net="12.50", opened=1)
        n.poll()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("posisi terkonfirmasi +2", self.sent[0])
        self.assertIn("posisi tertutup +2", self.sent[0])
        self.assertIn("Net tertutup kumulatif=12.50 USD", self.sent[0])
        self.assertIn("BUKAN profit satu transaksi", self.sent[0])
        n.poll()
        self.assertEqual(len(self.sent), 1)
        path.write_bytes(SNAPSHOT.encode() + b"partial")
        n.poll()
        self.snapshot(filled=3, closed=3, net="9.50")
        n.sender = lambda message: (_ for _ in ()).throw(TimeoutError())
        with self.assertRaises(TimeoutError):
            n.poll()
        self.snapshot(filled=4, closed=4, net="10.00")
        self.notifier().poll()
        self.assertEqual(len(self.sent), 3)
        self.assertIn("9.50 USD", self.sent[1])
        self.assertIn("10.00 USD", self.sent[2])

    def test_user_facing_notifications_are_indonesian(self):
        n = self.notifier()
        n.poll()
        self.append(audit())
        n.poll()
        self.assertIn("Permintaan entry", self.sent[0])
        self.snapshot(filled=1, closed=1, net="1.50")
        n.poll()
        self.assertIn("Net tertutup kumulatif", self.sent[-1])
        self.assertIn("BUKAN profit satu transaksi", self.sent[-1])

    def test_transport_rejects_missing_or_wrong_ack_destination(self):
        self.notifier()
        module = self.module
        sender = module.TelegramSender("123456789:" + "C" * 35, "-1001234567890", 42)
        class Response:
            def __init__(self, value): self.value = value
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({"ok": True, "result": self.value}).encode()
        cases = [
            {"message_id": 123},
            {"message_id": 123, "chat": {"id": -1001234567890}},
            {"message_id": 123, "chat": {"id": -1001234567899}, "message_thread_id": 42},
            {"message_id": 123, "chat": {"id": -1001234567890}, "message_thread_id": 43},
            {"message_id": 0, "chat": {"id": -1001234567890}, "message_thread_id": 42},
        ]
        for value in cases:
            with self.subTest(value=value):
                sender.open_request = lambda *args, value=value, **kwargs: Response(value)
                with self.assertRaises(module.DeliveryError):
                    sender("test")

    def test_transport_requires_explicit_destination_and_acknowledgement(self):
        from unittest.mock import patch
        self.notifier()
        import sys
        module = sys.modules.get("telegram_notifier")
        # Reload the script as a normal module for transport/CLI injection.
        import types
        module = types.ModuleType("notifier_under_test")
        exec(compile((ROOT / "tools/telegram_notifier.py").read_text(), "notifier", "exec"), module.__dict__)
        token = "123456789:" + "A" * 35
        with self.assertRaises(ValueError):
            module.TelegramSender.from_env({"TELEGRAM_BOT_TOKEN": token})
        env = {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": "-1001234567890", "TELEGRAM_THREAD_ID": "42"}
        sender = module.TelegramSender.from_env(env)
        calls = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'{"ok":true,"result":{"message_id":123,"chat":{"id":-1001234567890},"message_thread_id":42}}'
        def open_request(request, timeout):
            calls.append((request, timeout))
            return Response()
        sender.open_request = open_request
        sender("TEST SERVICE — no trade")
        body = json.loads(calls[0][0].data)
        self.assertEqual(body["chat_id"], "-1001234567890")
        self.assertEqual(body["message_thread_id"], 42)
        self.assertNotIn("parse_mode", body)
        self.assertTrue(body["protect_content"])
        def timeout(*args, **kwargs): raise TimeoutError(token)
        sender.open_request = timeout
        with self.assertRaises(module.DeliveryError) as caught:
            sender("test")
        self.assertNotIn(token, str(caught.exception))

    def test_cli_dry_run_self_test_is_labelled_and_never_advances_cursor(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout, redirect_stderr
        n = self.notifier()
        module = self.module
        n.poll()
        self.append(audit())
        before = (self.state / "cursor.json").read_bytes()
        output = io.StringIO()
        args = ["--source-dir", str(self.source), "--state-dir", str(self.state), "--once", "--dry-run"]
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(module.main(args), 0)
            self.assertEqual(module.main(["--self-test", "--dry-run"]), 0)
        self.assertIn("Permintaan entry", output.getvalue())
        self.assertIn("UJI SERVIS", output.getvalue())
        self.assertIn("BUKAN TRANSAKSI", output.getvalue())
        self.assertEqual((self.state / "cursor.json").read_bytes(), before)
        with patch.dict("os.environ", {}, clear=True), redirect_stderr(io.StringIO()):
            self.assertNotEqual(module.main(["--self-test"]), 0)

    def test_parent_env_and_self_test_ack_are_reported_without_token(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout
        self.notifier()
        module = self.module
        token = "123456789:" + "B" * 35
        token_file = self.base / "bot-token"
        token_file.write_text(token)
        env = {"TELEGRAM_BOT_TOKEN_FILE": str(token_file), "TELEGRAM_CHAT_ID": "-1001234567890", "TELEGRAM_THREAD_ID": "42", "GOLDSHIELD_FILES_DIR": str(self.source), "GOLDSHIELD_STATE_DIR": str(self.state)}
        sender = module.TelegramSender.from_env(env)
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'{"ok":true,"result":{"message_id":321,"chat":{"id":-1001234567890},"message_thread_id":42}}'
        sender.open_request = lambda *args, **kwargs: Response()
        out = io.StringIO()
        with patch.dict("os.environ", env, clear=True), patch.object(module.TelegramSender, "from_env", return_value=sender), redirect_stdout(out):
            self.assertEqual(module.main(["--self-test"]), 0)
        ack = json.loads(out.getvalue())
        self.assertEqual(ack, {"message_id": 321, "chat_id": "-1001234567890", "thread_id": 42})
        self.assertNotIn(token, out.getvalue())

    def test_unexpected_real_snapshot_prevents_any_audit_send(self):
        n = self.notifier()
        n.poll()
        before = self.file.read_bytes()
        self.snapshot(account_mode="REAL")
        self.append(audit())
        n.poll()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.file.read_bytes(), before + audit())

    def test_invalid_audit_schema_is_not_consumed(self):
        n = self.notifier()
        n.poll()
        self.file.write_bytes(b"not,the,audit,header\r\n" + audit())
        before = (self.state / "cursor.json").read_bytes()
        with self.assertRaises(ValueError):
            n.poll()
        self.assertEqual(self.sent, [])
        self.assertEqual((self.state / "cursor.json").read_bytes(), before)

    def test_preview_creates_no_state_and_rejects_source_state_overlap(self):
        from unittest.mock import patch
        from contextlib import redirect_stderr
        self.notifier()
        module = self.module
        preview = self.base / "new-preview-state"
        module.Notifier(self.source, preview, self.sent.append, dry_run=True).poll()
        self.assertFalse(preview.exists())
        with patch.dict("os.environ", {}, clear=True), redirect_stderr(io.StringIO()):
            self.assertEqual(module.main(["--source-dir", str(self.source), "--state-dir", str(self.source / "state"), "--once", "--dry-run"]), 2)
        self.assertFalse((self.source / "state").exists())

    def test_history_outage_alert_does_not_repeat_for_routine_state_changes(self):
        n = self.notifier()
        n.poll()
        for state in ("READY", "SIGNAL_PENDING", "READY", "SIGNAL_PENDING"):
            self.snapshot(trial_status="HISTORY_UNAVAILABLE_REVIEW_REQUIRED", core_state=state)
            n.poll()
        self.assertEqual(len(self.sent), 1)

    def test_history_unavailable_never_invents_zero_net_or_closed_positions(self):
        self.snapshot(filled=2, closed=1, net="7.00", opened=1)
        n = self.notifier()
        n.poll()
        self.snapshot(trial_status="HISTORY_UNAVAILABLE_REVIEW_REQUIRED")
        n.poll()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("riwayat tidak tersedia", self.sent[0])
        self.assertNotIn("Net tertutup kumulatif=", self.sent[0])
        self.assertNotIn("posisi tertutup +", self.sent[0])
        self.snapshot(filled=2, closed=1, net="7.00", opened=1)
        n.poll()
        self.assertIn("Riwayat pulih", self.sent[-1])
        self.assertNotIn("posisi terkonfirmasi +", self.sent[-1])

    def test_btcusd_crypto_symbol_notifications(self):
        self.snapshot(filled=1, opened=1, symbol="BTCUSDm")
        n = self.notifier()
        n.poll()
        self.assertEqual(self.sent, [])
        self.snapshot(filled=2, closed=1, net="45.50", opened=1, symbol="BTCUSDm")
        n.poll()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("BTCUSDm", self.sent[0])
        self.assertIn("posisi terkonfirmasi +1", self.sent[0])
        self.assertIn("posisi tertutup +1", self.sent[0])
        self.assertIn("Net tertutup kumulatif=45.50 USD", self.sent[0])

    def test_signal_notification_for_buy_and_sell_and_hold_silent(self):
        n = self.notifier()
        n.poll()
        # HOLD should be silent
        self.append(audit(event="SIGNAL", details="GS_HOLD model=GS_BASELINE close=75900.0 fast=75800.0 slow=75700.0 rsi=50.0 atr=80.0", reason="HOLD_SPREAD_LIMIT", symbol="BTCUSDm"))
        n.poll()
        self.assertEqual(self.sent, [])
        # BUY signal should notify
        self.append(audit(event="SIGNAL", details="GS_BUY model=GS_BASELINE close=75944.38 fast=75860.74 slow=75837.35 rsi=57.52 atr=84.56", reason="CANDIDATE_BASELINE_EMA_RSI", symbol="BTCUSDm"))
        n.poll()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Sinyal BUY terdeteksi", self.sent[0])
        self.assertIn("BTCUSDm", self.sent[0])
        self.assertIn("CANDIDATE_BASELINE_EMA_RSI", self.sent[0])
        self.assertIn("Harga: 75944.38", self.sent[0])
        self.assertIn("RSI: 57.52", self.sent[0])

    def test_daily_recap_generation(self):
        self.notifier()
        self.snapshot(filled=5, closed=5, net="15.20", opened=0)
        recap = self.module.generate_daily_recap(self.source, target_date="2026.11.08")
        self.assertIsNotNone(recap)
        self.assertIn("REKAPITULASI TRADING HARIAN", recap)
        self.assertIn("Tanggal: 2026.11.08", recap)
        self.assertIn("Total Order Selesai: 5 Transaksi", recap)
        self.assertIn("+15.20 USD", recap)
        self.assertIn("Status Robot: Berjalan Normal", recap)


if __name__ == "__main__":
    unittest.main()
