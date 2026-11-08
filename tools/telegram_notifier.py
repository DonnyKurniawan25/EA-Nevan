#!/usr/bin/env python3
"""Read-only GoldShield CSV observer. No MT5 API, polling bot, or trade commands."""
import csv
import io
import json
import os
from pathlib import Path
import re
import tempfile

AUDIT_HEADER = "event_id,server_time,utc_time,clock_source,event,symbol,candle_id_server,reason_code,details".split(",")
LABELS = {
    "ORDER_INTENT": "Mempersiapkan order baru (Intent entry)",
    "ORDER_RESULT": "Permintaan entry — BUKAN konfirmasi posisi (sedang diproses broker)",
    "ORDER_CHECK": "Pemeriksaan gagal: Preflight entry ditolak broker",
    "FILL_CONFIRMED": "Posisi terkonfirmasi aktif di pasar broker",
    "CLOSE_RESULT": "Permintaan tutup order sedang diproses broker",
    "EXIT_CONFIRMED": "Posisi selesai ditutup bersih di broker",
    "POSITION_CLOSED": "Pembaruan broker: Posisi sudah selesai ditutup",
    "STORAGE_ERROR": "Peringatan: Kesalahan penyimpanan pengaman",
    "INIT_FAILED": "Peringatan: Inisialisasi robot gagal",
    "TIME_PROFIT_EXIT": "Target waktu tercapai: Posisi ditutup saat untung",
    "EARLY_REVERSAL_EXIT": "Pembalikan arah tren terdeteksi: Cut loss dini",
    "STOP_MODIFY": "Proteksi modal: Stop Loss digeser ke Break-Even (Rp0 risiko)",
}
ALERT_STATES = {"PAUSED_RISK", "ERROR_BLOCKED", "SAFE_MODE", "PAUSED_MANUAL", "PAUSED_VOLATILITY"}
REASONS = set("""BASELINE_RULES RECONCILIATION_REQUIRED BROKER_PREFLIGHT_REJECTED BROKER_POSITION_PRESENT
VERIFY_RESIDUAL_POSITION NO_RESIDUAL_EA_POSITION BROKER_SNAPSHOT_EMPTY RISK_LATCH_WRITE_FAILED
EQUITY_REFERENCE_FLOOR MARGIN_EMERGENCY POSITION_STOP_OR_LOSS_EMERGENCY PERSISTENT_HARD_RISK_LATCH
ACCOUNT_CHANGED_REATTACH_REQUIRED DISCONNECTED_SERVER_STOPS_ONLY
PERSISTENT_BLOCK_OR_UNCONFIRMED_ORDER_REVIEW_REQUIRED DEMO20_LIMIT_REACHED_NO_MORE_ENTRIES
DEMO20_ACCOUNT_OR_LIMIT_INVALID DEMO20_COUNTER_INVALID DEMO20_SLOT_RESERVATION_FAILED
DEMO20_SLOT_VERIFY_FAILED ORDER_INTENT_AUDIT_WRITE_FAILED BROKER_PREFLIGHT_MARGIN_LIMIT
DURABLE_ENTRY_INTENT_FAILED CLOSE_RETRY_LIMIT_OPERATOR_REQUIRED CLOSE_RETRY_BACKOFF
CLOSE_TICKET_NO_LONGER_PRESENT CLOSE_OWNERSHIP_REJECTED INDICATOR_HANDLE_ERROR TIMER_ERROR
HOLD_VOLATILITY_OR_GAP AUTO_ENTRY_DISABLED HOLD_STALE_TICK HOLD_TICK_UNAVAILABLE
TIME_EXIT_PROFIT HOLD_DURATION_TARGET_UNREACHED EARLY_REVERSAL_EXIT TREND_INVALIDATED_CUT_LOSS BREAK_EVEN TRAILING_STOP""".split())

EVENT_ICONS = {
    "SIGNAL": "🔔",
    "ORDER_INTENT": "📝",
    "ORDER_RESULT": "📤",
    "ORDER_CHECK": "⚠️",
    "FILL_CONFIRMED": "✅",
    "CLOSE_RESULT": "🔄",
    "EXIT_CONFIRMED": "🏁",
    "POSITION_CLOSED": "🏁",
    "STORAGE_ERROR": "❌",
    "INIT_FAILED": "❌",
    "TIME_PROFIT_EXIT": "🎯",
    "EARLY_REVERSAL_EXIT": "⚠️",
    "PARTIAL_CLOSE": "🎯",
    "STOP_MODIFY": "🛡️",
    "STATE": "ℹ️",
}

REASON_DESCRIPTIONS = {
    "TIME_EXIT_PROFIT": "Target waktu 30 menit tercapai (amankan profit)",
    "HOLD_DURATION_TARGET_UNREACHED": "Target waktu tahan selesai saat posisi untung",
    "TREND_INVALIDATED_CUT_LOSS": "Pembalikan tren terdeteksi (cut loss dini)",
    "BREAK_EVEN": "Proteksi modal: Stop Loss digeser ke harga modal",
    "TAKE_PROFIT_1": "Target keuntungan 1 tercapai (50% posisi ditutup & profit diamankan)",
    "PARTIAL_TP_BREAK_EVEN": "Proteksi modal: Stop Loss sisa posisi digeser ke harga modal",
    "TP1_LOCK_BREAK_EVEN": "Target keuntungan 1 tercapai: Stop Loss dikunci ke harga modal",
    "HOLD_NO_FRESH_TRIGGER": "Bukan pemicu segar (mencegah entri di pucuk tren lama)",
    "TRAILING_STOP": "Trailing Stop aktif (mengunci keuntungan bertahap)",
    "BROKER_SNAPSHOT_EMPTY": "Posisi selesai ditutup di broker",
    "BROKER_POSITION_PRESENT": "Posisi aktif di broker",
    "BASELINE_RULES": "Sesuai aturan strategi indikator",
    "RECONCILIATION_REQUIRED": "Permintaan diproses broker",
    "CANDIDATE_BASELINE_EMA_RSI": "Validasi indikator EMA & RSI",
    "HOLD_DAILY_ENTRY_LIMIT": "Batas kuota harian tercapai (mencegah overtrade)",
    "HOLD_SPREAD_ATR_EXCESSIVE": "Spread broker melebar melebihi batas wajar ATR",
    "HOLD_MIDNIGHT_ROLLOVER": "Jam rollover pergantian hari broker (spread melebar ekstrem)",
    "HOLD_SESSION_FILTER_CLOSED": "Di luar jadwal jam sesi trading aktif",
    "HOLD_HTF_TREND_BEARISH": "Tren H1 sedang turun (bearish), sinyal beli M15 dibatalkan",
    "HOLD_HTF_TREND_BULLISH": "Tren H1 sedang naik (bullish), sinyal jual M15 dibatalkan",
    "HOLD_ADX_SIDEWAYS": "Pasar sedang sideways/flat (kekuatan tren lemah, ADX < batas aman)",
    "DISCONNECTED_SERVER_STOPS_ONLY": "Koneksi terputus (Stop Loss server aktif)",
    "EQUITY_REFERENCE_FLOOR": "Batas pengaman modal minimum",
}

KEY_TRANSLATIONS = {
    "ticket": "Tiket",
    "order": "Nomor Order",
    "deal": "Nomor Deal",
    "identifier": "ID Posisi",
    "lots": "Volume",
    "entry": "Harga Masuk",
    "sl": "Batas Rugi (SL)",
    "tp": "Target Untung (TP)",
    "profit": "Hasil Transaksi (PnL)",
    "retcode": "Status Broker",
    "budget": "Alokasi Modal",
    "risk_est": "Estimasi Risiko",
    "margin_est": "Estimasi Margin",
    "close_vol": "Volume Ditutup",
    "adx": "Kekuatan Tren (ADX)",
}


def audit_message(row):
    if len(row) != len(AUDIT_HEADER):
        return None, None
    item = dict(zip(AUDIT_HEADER, row))
    event = item["event"]
    label = LABELS.get(event)
    signature = None
    symbol = item["symbol"] if re.fullmatch(r"(?:XAUUSD|BTCUSD)[A-Za-z0-9._-]{0,8}", item["symbol"]) else "[symbol redacted]"
    if event == "STATE":
        match = re.fullmatch(r"[A-Z_]+ -> ([A-Z_]+)", item["details"])
        if not match or match[1] not in ALERT_STATES:
            return None, None
        label = "Status pengaman: " + match[1]
        signature = match[1] + ":" + (item["reason_code"] if item["reason_code"] in REASONS else "OTHER")
    elif event == "STOP_MODIFY" and item.get("reason_code") == "TRAILING_STOP":
        label = "Kunci keuntungan: Stop Loss digeser (Trailing Stop)"
    elif event == "SIGNAL":
        match = re.match(r"^(GS_BUY|GS_SELL)\b", item["details"])
        if not match:
            return None, None
        side = "BUY" if match.group(1) == "GS_BUY" else "SELL"
        side_id = "Beli (BUY)" if side == "BUY" else "Jual (SELL)"
        label = f"Sinyal {side} terdeteksi"
        reason = item["reason_code"] if item["reason_code"] in REASONS | {"CANDIDATE_BASELINE_EMA_RSI"} else "OTHER_REASON_REDACTED"
        metrics = dict(re.findall(r"\b(close|fast|slow|rsi|atr)=([0-9]+(?:\.[0-9]+)?)", item["details"]))
        icon = EVENT_ICONS.get("SIGNAL", "🔔")
        lines = [
            f"{icon} GoldShield DEMO | {label}",
            f"Pasar: {symbol} | {reason}",
            f"• Aksi: {side_id}",
        ]
        if "close" in metrics:
            lines.append(f"• Harga: {metrics['close']}")
        if "rsi" in metrics:
            lines.append(f"• RSI: {metrics['rsi']}")
        if "atr" in metrics:
            lines.append(f"• ATR: {metrics['atr']}")
        return ("\n".join(lines))[:1500], None
    if not label:
        return None, None
    # Discard arbitrary text; only exact reason constants and numeric detail keys.
    reason = item["reason_code"] if item["reason_code"] in REASONS else "OTHER_REASON_REDACTED"
    icon = EVENT_ICONS.get(event, "ℹ️")
    reason_desc = REASON_DESCRIPTIONS.get(reason)
    if reason_desc:
        reason_text = f"{reason} ({reason_desc})"
    else:
        reason_text = reason

    formatted_vals = []
    for key, value in re.findall(r"(?:^|\s)(lots|entry|sl|tp|profit|adx|close_vol|budget|risk_est|margin_est|retcode|order|deal|ticket|identifier)=(-?[0-9]{1,20}(?:\.[0-9]{1,8})?)(?=\s|$)", item["details"]):
        lbl = KEY_TRANSLATIONS.get(key, key)
        if key == "retcode" and value == "10009":
            formatted_vals.append(f"• {lbl}: 10009 (Sukses)")
        elif key == "ticket":
            formatted_vals.append(f"• {lbl}: #{value}")
        elif key == "lots":
            formatted_vals.append(f"• {lbl}: {value} Lot")
        elif key == "profit":
            try:
                val_float = float(value)
                if val_float > 0:
                    formatted_vals.append(f"• {lbl}: +{value} USD (Untung)")
                elif val_float < 0:
                    formatted_vals.append(f"• {lbl}: {value} USD (Rugi)")
                else:
                    formatted_vals.append(f"• {lbl}: {value} USD (Impas / $0)")
            except ValueError:
                formatted_vals.append(f"• {lbl}: {value} USD")
        else:
            formatted_vals.append(f"• {lbl}: {value}")

    lines = [
        f"{icon} GoldShield DEMO | {label}",
        f"Pasar: {symbol} | {reason_text}",
    ]
    if formatted_vals:
        lines.extend(formatted_vals[:12])

    if event == "TIME_PROFIT_EXIT":
        lines.append("Penjelasan: Waktu tahan 30 menit selesai, posisi ditutup saat untung.")
    elif event == "EARLY_REVERSAL_EXIT":
        lines.append("Penjelasan: Indikator mendeteksi tren berbalik arah, cut loss dini dijalankan.")
    elif event == "STOP_MODIFY":
        if "BREAK_EVEN" in reason:
            lines.append("Penjelasan: Stop Loss digeser ke harga masuk. Posisi aman, risiko kerugian modal kini $0.00.")
        elif "TRAILING_STOP" in reason:
            lines.append("Penjelasan: Trailing Stop menggeser Stop Loss mengikuti arah profit untuk mengunci keuntungan bertahap.")
    elif event == "FILL_CONFIRMED":
        lines.append("Penjelasan: Order telah terisi aktif di broker dan dipantau sistem.")
    elif event == "POSITION_CLOSED":
        lines.append("Penjelasan: Posisi sudah selesai ditutup di broker.")

    return ("\n".join(lines))[:1500], signature



SNAPSHOT_HEADER = "time_server,account_mode,symbol,limit,entry_submissions,filled_positions,closed_positions,wins,losses,net_closed,currency,open_positions,trial_status,core_state,core_reason".split(",")
TRIAL_STATES = {"RUNNING_WAIT_VALID_SIGNAL", "LIMIT_REACHED_MANAGING_LAST_POSITION", "LIMIT_REACHED_FLAT", "HISTORY_UNAVAILABLE_REVIEW_REQUIRED"}


def snapshot_data(path):
    from decimal import Decimal, InvalidOperation
    rows = records(path.read_bytes())
    if len(rows) != 2 or rows[0][1] != SNAPSHOT_HEADER or len(rows[1][1]) != len(SNAPSHOT_HEADER):
        return None
    item = dict(zip(SNAPSHOT_HEADER, rows[1][1]))
    if item["account_mode"] != "DEMO" or item["trial_status"] not in TRIAL_STATES:
        return None
    if not re.fullmatch(r"(?:XAUUSD|BTCUSD)[A-Za-z0-9._-]{0,8}", item["symbol"]) or not re.fullmatch(r"[A-Z]{3}", item["currency"]):
        return None
    for key in ("limit", "entry_submissions", "filled_positions", "closed_positions", "wins", "losses", "open_positions"):
        if not re.fullmatch(r"[0-9]{1,8}", item[key]):
            return None
        item[key] = int(item[key])
    try:
        value = Decimal(item["net_closed"])
        if not value.is_finite() or len(item["net_closed"]) > 30:
            return None
    except InvalidOperation:
        return None
    # Only retain permitted fields, never raw snapshot contents.
    item["core_state"] = item["core_state"] if item["core_state"] in ALERT_STATES | {"READY", "BASKET_ACTIVE", "COOLDOWN", "OPENING", "RECOVERY", "SIGNAL_PENDING", "INIT", "BASKET_EXITING"} else "OTHER"
    item["core_reason"] = item["core_reason"] if item["core_reason"] in REASONS else "OTHER"
    del item["time_server"]
    return item


def snapshot_message(old, new):
    if new["trial_status"] == "HISTORY_UNAVAILABLE_REVIEW_REQUIRED":
        if old and old["trial_status"] == "HISTORY_UNAVAILABLE_REVIEW_REQUIRED":
            return None
        return "⚠️ GoldShield DEMO | riwayat tidak tersedia — PERLU PEMERIKSAAN; fill/close/net tidak disimpulkan"
    if old and old["trial_status"] == "HISTORY_UNAVAILABLE_REVIEW_REQUIRED":
        return ("ℹ️ GoldShield DEMO | Riwayat pulih; hanya penghitung kumulatif, bukan kesimpulan transaksi baru\n"
                + "• Net tertutup kumulatif=" + new["net_closed"] + " " + new["currency"] + " — BUKAN profit satu transaksi")
    pieces = []
    if old is None:
        pieces.append("• Status aktif pertama yang teramati (bukan bukti transaksi baru)")
    else:
        for key, label in (("filled_positions", "posisi terkonfirmasi"), ("closed_positions", "posisi tertutup")):
            delta = new[key] - old[key]
            if delta > 0:
                pieces.append(f"• {label} +{delta}")
            elif delta < 0:
                pieces.append("• PENGHITUNG TURUN / RIWAYAT BERUBAH; transaksi tidak disimpulkan")
        if new["entry_submissions"] != old["entry_submissions"]:
            pieces.append(f"• Pengiriman entry={new['entry_submissions']} (bukan konfirmasi fill)")
        if new["core_state"] in ALERT_STATES and (new["core_state"], new["core_reason"]) != (old["core_state"], old["core_reason"]):
            pieces.append(f"• Status pengaman: {new['core_state']} | {new['core_reason']}")
        if new["trial_status"] != old["trial_status"]:
            pieces.append(f"• Status sesi: {new['trial_status']}")
    if not pieces and (old is None or new["net_closed"] == old["net_closed"]):
        return None
    pieces.append(f"• Net tertutup kumulatif={new['net_closed']} {new['currency']} — BUKAN profit satu transaksi")
    pieces.append("Catatan: Angka di atas adalah akumulasi keuntungan/kerugian dari seluruh order yang telah selesai.")
    return ("📊 GoldShield DEMO status | " + new["symbol"] + "\n" + "\n".join(pieces))[:1500]


def records(data):
    """Only newline-terminated, complete CSV records, with byte offsets."""
    end = data.rfind(b"\n") + 1
    if not end:
        return []
    result = []
    offset = 0
    chunk = b""
    for line in data[:end].splitlines(keepends=True):
        chunk += line
        try:
            rows = list(csv.reader(io.StringIO(chunk.decode("cp1252", errors="replace"), newline=""), strict=True))
        except csv.Error:
            continue
        offset += len(chunk)
        if len(rows) == 1:
            result.append((offset, rows[0]))
        chunk = b""
    return result


class DeliveryError(Exception):
    """Safe for logging: never includes an URL, token, or response body."""


class TelegramSender:
    def __init__(self, token, chat_id, thread_id, timeout=15):
        import urllib.request
        self._token = token
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.timeout = timeout
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.open_request = urllib.request.build_opener(NoRedirect()).open

    @classmethod
    def from_env(cls, env, timeout=15):
        token = env.get("TELEGRAM_BOT_TOKEN", "")
        token_file = env.get("TELEGRAM_BOT_TOKEN_FILE", "")
        if token and token_file:
            raise ValueError("Set exactly one bot token source")
        if token_file:
            try:
                token = Path(token_file).read_text().strip()
            except OSError:
                raise ValueError("Cannot read bot token file") from None
        chat = env.get("TELEGRAM_CHAT_ID", "")
        thread = env.get("TELEGRAM_THREAD_ID", "")
        if not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,100}", token):
            raise ValueError("Invalid bot token configuration")
        if not re.fullmatch(r"-?[0-9]{1,20}", chat) or int(chat) == 0 or not re.fullmatch(r"[0-9]{1,12}", thread) or int(thread) <= 0:
            raise ValueError("Explicit numeric Telegram chat and positive topic ID required")
        return cls(token, chat, int(thread), timeout)

    def __call__(self, text):
        import urllib.request
        request = urllib.request.Request(
            "https://api.telegram.org/bot" + self._token + "/sendMessage",
            data=json.dumps({"chat_id": self.chat_id, "message_thread_id": self.thread_id,
                             "text": text[:1500], "protect_content": True,
                             "link_preview_options": {"is_disabled": True}}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self.open_request(request, timeout=self.timeout) as response:
                result = json.loads(response.read(65537))
            if result.get("ok") is not True or type(result.get("result", {}).get("message_id")) is not int:
                raise ValueError("Missing Telegram acknowledgement")
            reply = result["result"]
            if reply["message_id"] <= 0:
                raise ValueError("Non-durable Telegram message acknowledgement")
            if str(reply.get("chat", {}).get("id")) != self.chat_id:
                raise ValueError("Unexpected acknowledged chat")
            if reply.get("message_thread_id") != self.thread_id:
                raise ValueError("Unexpected acknowledged topic")
            return {"message_id": reply["message_id"], "chat_id": self.chat_id, "thread_id": self.thread_id}
        except Exception:
            raise DeliveryError("Telegram delivery unacknowledged; retained for retry") from None


class Notifier:
    def __init__(self, source, state_dir, sender, dry_run=False):
        self.source = Path(source).resolve()
        self.directory = Path(state_dir).resolve()
        if not dry_run:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.directory / "cursor.json"
        self.sender = sender
        self.dry_run = dry_run
        self.state = json.loads(self.path.read_text()) if self.path.exists() else None

    def save(self):
        if self.dry_run:
            return
        fd, name = tempfile.mkstemp(prefix=".cursor-", dir=self.directory)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(self.state, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
            directory = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def identity(path):
        stat = path.stat()
        return f"{stat.st_dev}:{stat.st_ino}"

    @staticmethod
    def cursor(data, offset):
        import hashlib
        return {"offset": offset, "anchor": hashlib.sha256(data[max(0, offset - 256):offset]).hexdigest()}

    def poll(self):
        files = sorted(p for p in self.source.glob("GS2.*.csv*") if re.fullmatch(r"GS2\.[0-9A-Fa-f]{16}\.csv(?:\.[0-9]+)?", p.name))
        snapshots = sorted(p for p in self.source.glob("demo20_*.csv") if re.fullmatch(r"demo20_[0-9]+\.csv", p.name))
        if self.state is None:
            self.state = {"version": 1, "audit": {}, "snapshots": {}, "pending": None}
            for path in snapshots:
                self.state["snapshots"][path.name] = snapshot_data(path)
            for path in files:
                data = path.read_bytes()
                rows = records(data)
                offset = rows[-1][0] if rows else 0
                self.state["audit"][self.identity(path)] = self.cursor(data, offset)
            self.save()
            return
        current = {path.name: snapshot_data(path) for path in snapshots}
        if not current or any(value is None for value in current.values()):
            return  # Fail closed: audit has no account_mode, so require current DEMO evidence.
        self.deliver_pending()
        for path in files:
            key = self.identity(path)
            data = path.read_bytes()
            header = records(data[:data.find(b"\n") + 1])
            if not header:
                continue
            if header[0][1] != AUDIT_HEADER:
                raise ValueError("Unexpected audit schema")
            previous = self.state["audit"].get(key, self.cursor(data, 0))
            start = previous["offset"]
            if len(data) < start or self.cursor(data, start)["anchor"] != previous["anchor"]:
                start = 0
            alert = previous.get("alert")
            for size, row in records(data[start:]):
                message, signature = audit_message(row)
                if signature and signature == alert:
                    message = None
                if signature:
                    alert = signature
                value = self.cursor(data, start + size)
                value["alert"] = alert
                if message:
                    self.state["pending"] = {"message": message, "group": "audit", "key": key, "value": value}
                    self.save()
                    self.deliver_pending()
                else:
                    self.state["audit"][key] = value
                    self.save()

        for path in snapshots:
            value = snapshot_data(path)
            if value is None:
                continue
            previous = self.state["snapshots"].get(path.name)
            message = snapshot_message(previous, value)
            if message:
                self.state["pending"] = {"message": message, "group": "snapshots", "key": path.name, "value": value}
                self.save()
                self.deliver_pending()
            elif previous != value:
                self.state["snapshots"][path.name] = value
                self.save()

    def deliver_pending(self):
        pending = self.state.get("pending")
        if pending:
            self.sender(pending["message"])
            self.state[pending["group"]][pending["key"]] = pending["value"]
            self.state["pending"] = None
            self.save()


def main(argv=None):
    import argparse
    import fcntl
    import sys
    import time
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default=os.environ.get("GOLDSHIELD_FILES_DIR"), help="Read-only MQL5/Files/GoldShield directory")
    parser.add_argument("--state-dir", default=os.environ.get("GOLDSHIELD_STATE_DIR", "/var/lib/goldshield-notifier"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="No network and no cursor writes; preview only")
    parser.add_argument("--self-test", action="store_true", help="Send labelled service test only, no trade event")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    lock = None
    try:
        if not 0.1 <= args.interval <= 3600 or not 1 <= args.timeout <= 120:
            raise ValueError("Invalid interval or timeout")
        sender = print if args.dry_run else TelegramSender.from_env(os.environ, args.timeout)
        if args.self_test:
            ack = sender("GoldShield UJI SERVIS — BUKAN TRANSAKSI. Tes koneksi notifier read-only; bukan order, fill, atau laporan profit.")
            if not args.dry_run:
                print(json.dumps(ack, sort_keys=True))
            return 0
        if not args.source_dir or not Path(args.source_dir).is_dir():
            raise ValueError("Existing source directory required")
        source, state = Path(args.source_dir).resolve(), Path(args.state_dir).resolve()
        if state == source or source in state.parents or state in source.parents:
            raise ValueError("Source and state directories must be disjoint")
        if not args.dry_run:
            state.mkdir(mode=0o700, parents=True, exist_ok=True)
            lock = (state / "notifier.lock").open("a")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        observer = Notifier(source, state, sender, dry_run=args.dry_run)
        failures = 0
        while True:
            try:
                observer.poll()
                failures = 0
            except DeliveryError:
                print("Telegram delivery unacknowledged; retry pending", file=sys.stderr)
                failures = min(failures + 1, 8)
                if args.once:
                    return 1
            if args.once:
                return 0
            time.sleep(min(300, args.interval * (2 ** failures)))
    except (OSError, ValueError, KeyError, TypeError):
        # Do not include exception strings: paths, credentials and remote data are untrusted.
        print("Notifier configuration/state/input unavailable; check configuration and permissions", file=sys.stderr)
        return 2
    except DeliveryError:
        print("Telegram service test unacknowledged", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if lock:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
