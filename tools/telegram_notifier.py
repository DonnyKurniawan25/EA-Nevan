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
    "ORDER_INTENT": "Intent entry — belum dikirim atau terisi di broker",
    "ORDER_RESULT": "Permintaan entry — BUKAN konfirmasi posisi",
    "ORDER_CHECK": "Preflight entry ditolak",
    "FILL_CONFIRMED": "Posisi terkonfirmasi dari snapshot broker",
    "CLOSE_RESULT": "Permintaan tutup — perlu rekonsiliasi",
    "EXIT_CONFIRMED": "Exit terkonfirmasi: tidak ada sisa posisi EA; net menunggu riwayat",
    "POSITION_CLOSED": "Posisi tidak ada pada snapshot broker; net menunggu riwayat",
    "STORAGE_ERROR": "Kesalahan penyimpanan pengaman",
    "INIT_FAILED": "Inisialisasi EA gagal",
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
HOLD_VOLATILITY_OR_GAP AUTO_ENTRY_DISABLED HOLD_STALE_TICK HOLD_TICK_UNAVAILABLE""".split())


def audit_message(row):
    if len(row) != len(AUDIT_HEADER):
        return None, None
    item = dict(zip(AUDIT_HEADER, row))
    event = item["event"]
    label = LABELS.get(event)
    signature = None
    if event == "STATE":
        match = re.fullmatch(r"[A-Z_]+ -> ([A-Z_]+)", item["details"])
        if not match or match[1] not in ALERT_STATES:
            return None, None
        label = "Status pengaman: " + match[1]
        signature = match[1] + ":" + (item["reason_code"] if item["reason_code"] in REASONS else "OTHER")
    if not label:
        return None, None
    # Discard arbitrary text; only exact reason constants and numeric detail keys.
    reason = item["reason_code"] if item["reason_code"] in REASONS else "OTHER_REASON_REDACTED"
    symbol = item["symbol"] if re.fullmatch(r"XAUUSD[A-Za-z0-9._-]{0,8}", item["symbol"]) else "[symbol redacted]"
    values = []
    for key, value in re.findall(r"(?:^|\s)(lots|entry|sl|tp|budget|risk_est|margin_est|retcode|order|deal|ticket|identifier)=(-?[0-9]{1,20}(?:\.[0-9]{1,8})?)(?=\s|$)", item["details"]):
        values.append(key + "=" + value)
    return ("GoldShield DEMO | " + label + "\n" + symbol + " | " + reason + ("\n" + " ".join(values[:12]) if values else ""))[:1500], signature



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
    if not re.fullmatch(r"XAUUSD[A-Za-z0-9._-]{0,8}", item["symbol"]) or not re.fullmatch(r"[A-Z]{3}", item["currency"]):
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
        return "GoldShield DEMO | riwayat tidak tersedia — PERLU PEMERIKSAAN; fill/close/net tidak disimpulkan"
    if old and old["trial_status"] == "HISTORY_UNAVAILABLE_REVIEW_REQUIRED":
        return ("GoldShield DEMO | Riwayat pulih; hanya penghitung kumulatif, bukan kesimpulan transaksi baru\n"
                + "Net tertutup kumulatif=" + new["net_closed"] + " " + new["currency"] + " — BUKAN profit satu transaksi")
    pieces = []
    if old is None:
        pieces.append("Status aktif pertama yang teramati (bukan bukti transaksi baru)")
    else:
        for key, label in (("filled_positions", "posisi terkonfirmasi"), ("closed_positions", "posisi tertutup")):
            delta = new[key] - old[key]
            if delta > 0:
                pieces.append(label + " +" + str(delta))
            elif delta < 0:
                pieces.append("PENGHITUNG TURUN / RIWAYAT BERUBAH; transaksi tidak disimpulkan")
        if new["entry_submissions"] != old["entry_submissions"]:
            pieces.append("pengiriman entry=" + str(new["entry_submissions"]) + " (bukan konfirmasi fill)")
        if new["core_state"] in ALERT_STATES and (new["core_state"], new["core_reason"]) != (old["core_state"], old["core_reason"]):
            pieces.append("Status pengaman: " + new["core_state"] + " | " + new["core_reason"])
        if new["trial_status"] != old["trial_status"]:
            pieces.append(new["trial_status"])
    if not pieces and (old is None or new["net_closed"] == old["net_closed"]):
        return None
    pieces.append("Net tertutup kumulatif=" + new["net_closed"] + " " + new["currency"] + " — BUKAN profit satu transaksi")
    return ("GoldShield DEMO status | " + new["symbol"] + "\n" + "\n".join(pieces))[:1500]


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
