#!/usr/bin/env python3
"""GoldShield CSV observer; Telegram send-only by default, dedicated-bot polling opt-in."""
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
    "FRIDAY_PRE_CLOSE": "Proteksi akhir pekan: Posisi ditutup otomatis jelang libur bursa (Anti-Gap)",
    "RSI_EXTREME_PROFIT_EXIT": "Amankan keuntungan: Pucuk RSI ekstrim tercapai",
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
TIME_EXIT_PROFIT HOLD_DURATION_TARGET_UNREACHED EARLY_REVERSAL_EXIT TREND_INVALIDATED_CUT_LOSS BREAK_EVEN TRAILING_STOP
STEPPED_PROFIT_LOCK RSI_EXTREME_PROFIT_EXIT RSI_OVERBOUGHT_EXHAUSTION RSI_OVERSOLD_EXHAUSTION
HOLD_HTF_SLOPE_FLAT_OR_FALLING HOLD_HTF_SLOPE_FLAT_OR_RISING""".split())

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
    "FRIDAY_PRE_CLOSE": "🛡️",
    "RSI_EXTREME_PROFIT_EXIT": "💎",
    "STATE": "ℹ️",
}

REASON_DESCRIPTIONS = {
    "TIME_EXIT_PROFIT": "Target waktu 30 menit tercapai (amankan profit)",
    "HOLD_DURATION_TARGET_UNREACHED": "Target waktu tahan selesai saat posisi untung",
    "TREND_INVALIDATED_CUT_LOSS": "Pembalikan tren terdeteksi (cut loss dini)",
    "BREAK_EVEN": "Proteksi modal: Stop Loss digeser ke harga modal",
    "STEPPED_PROFIT_LOCK": "Kunci profit bertingkat (Stop Loss dinaikkan ke zona profit)",
    "RSI_OVERBOUGHT_EXHAUSTION": "Indikator RSI jenuh beli ekstrim (take profit penuh)",
    "RSI_OVERSOLD_EXHAUSTION": "Indikator RSI jenuh jual ekstrim (take profit penuh)",
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
    "HOLD_HTF_SLOPE_FLAT_OR_FALLING": "Kemiringan tren H1 mendatar/turun (batal BUY)",
    "HOLD_HTF_SLOPE_FLAT_OR_RISING": "Kemiringan tren H1 mendatar/naik (batal SELL)",
    "HOLD_ADX_SIDEWAYS": "Pasar sedang sideways/flat (kekuatan tren lemah, ADX < batas aman)",
    "HOLD_CANDLE_BEARISH": "Candle M15 Berwarna Merah (Menolak BUY)",
    "HOLD_CANDLE_BULLISH": "Candle M15 Berwarna Hijau (Menolak SELL)",
    "HOLD_CANDLE_UPPER_WICK_REJECTION": "Sumbu Atas Panjang / Rejection (Batal BUY)",
    "HOLD_CANDLE_LOWER_WICK_REJECTION": "Sumbu Bawah Panjang / Rejection (Batal SELL)",
    "HOLD_LOW_TICK_VOLUME": "Volume Pasar Rendah / Sepi (Batal Masuk)",
    "HOLD_FRIDAY_WEEKEND_APPROACHING": "Bursa libur akhir pekan segera tiba (menolak order baru)",
    "HOLD_OPPOSITE_DIRECTION_EXISTS": "Ada posisi aktif berlawanan arah (menolak hedging)",
    "HOLD_ATR_TOO_LOW_DEAD_MARKET": "Volatilitas ATR terlalu rendah / pasar mati",
    "HOLD_EMA_PENETRATION_INSUFFICIENT": "Penembusan EMA terlalu tipis / rawan whipsaw",
    "HOLD_PRICE_OVEREXTENDED": "Harga lonjak terlalu jauh dari EMA (anti-pucuk/lembah)",
    "HOLD_VOLUME_CLIMAX": "Volume ledakan abnormal (waspada climax / stop-hunt)",
    "HOLD_ADDON_EXISTING_NOT_PROFITABLE": "Tahan posisi tambahan (posisi pertama belum profit)",
    "HOLD_ADDON_TOO_CLOSE": "Tahan posisi tambahan (jarak terlalu dekat dengan posisi aktif)",
    "HOLD_ADX_MOMENTUM_FALLING": "Momentum ADX melemah / tren menurun (ADX < 25)",
    "HOLD_CANDLE_BODY_TOO_SMALL": "Badan candle M15 terlalu tipis / doji (menolak entry)",
    "HOLD_RSI_MOMENTUM_WEAK": "Momentum RSI ragu-ragu di dekat garis tengah 50",
    "WEEKEND_GAP_PREVENTION": "Penutupan otomatis sebelum bursa emas/forex tutup",
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
    elif event == "STOP_MODIFY" and item.get("reason_code") == "STEPPED_PROFIT_LOCK":
        label = "Kunci keuntungan: Stop Loss dinaikkan berjenjang (Stepped Profit Lock)"
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


def generate_daily_recap(source_dir, target_date=None):
    from datetime import datetime, timezone
    source = Path(source_dir)
    snapshots = sorted(source.glob("demo20_*.csv"))
    snap_data = None
    for p in snapshots:
        val = snapshot_data(p)
        if val and (snap_data is None or val.get("closed_positions", 0) >= snap_data.get("closed_positions", 0)):
            snap_data = val
    if not snap_data:
        return None

    balance = None
    equity = None
    acc_file = source / "account_live.csv"
    preflight = source / "server_preflight.csv"
    if acc_file.exists():
        try:
            lines = acc_file.read_text(errors="ignore").strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split(",")
                balance = float(parts[1])
                equity = float(parts[2])
        except Exception:
            pass
    if balance is None and preflight.exists():
        try:
            lines = preflight.read_text(errors="ignore").strip().splitlines()
            if len(lines) >= 2:
                hdr = lines[0].split(",")
                vals = lines[1].split(",")
                d = dict(zip(hdr, vals))
                balance = float(d.get("balance", 0.0))
                equity = float(d.get("equity", 0.0))
        except Exception:
            pass

    date_str = target_date or datetime.now(timezone.utc).strftime("%Y.%m.%d")
    total_closed = snap_data.get("closed_positions", 0)
    wins = snap_data.get("wins", 0)
    losses = snap_data.get("losses", 0)
    breakeven = max(0, total_closed - (wins + losses))
    win_rate = (wins / total_closed * 100.0) if total_closed > 0 else 0.0
    net_closed = float(snap_data.get("net_closed", 0.0))
    pnl_sign = "+" if net_closed >= 0 else ""
    pnl_icon = "🟢" if net_closed >= 0 else "🔴"
    curr = snap_data.get("currency", "USD")

    lines = [
        "📊 REKAPITULASI TRADING HARIAN",
        f"📅 Tanggal: {date_str} (Server UTC)",
        "━━━━━━━━━━━━━━━━━━━━",
        f"• Pasang Mata Uang: {snap_data.get('symbol', 'BTCUSDm')}",
        f"• Total Order Selesai: {total_closed} Transaksi",
        f"• Menang (Win): {wins} Transaksi ({win_rate:.1f}%)",
        f"• Kalah (Loss): {losses} Transaksi",
        f"• Impas (Break-Even): {breakeven} Transaksi",
        f"• Laba/Rugi Bersih: {pnl_sign}{net_closed:.2f} {curr} {pnl_icon}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if balance is not None and equity is not None:
        lines.append(f"💰 Saldo Akun: ${balance:,.2f} {curr}")
        lines.append(f"📈 Ekuitas Akun: ${equity:,.2f} {curr}")
    lines.append(f"🛡️ Kuota DEMO: {snap_data.get('entry_submissions', 0)}/{snap_data.get('limit', 20)} Transaksi")
    lines.append("⚙️ Status Robot: Berjalan Normal & Terproteksi Otomatis")
    return "\n".join(lines)[:1500]



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
    def __init__(self, token, chat_id, thread_id, timeout=15, *, polling_enabled=False):
        import urllib.request
        self._token = token
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.timeout = timeout
        self.polling_enabled = polling_enabled
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.open_request = urllib.request.build_opener(NoRedirect()).open

    @classmethod
    def from_env(cls, env, timeout=15):
        token = env.get("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")
        token_file = env.get("TELEGRAM_BOT_TOKEN_FILE", "").strip().strip('"').strip("'")
        if token and token_file:
            raise ValueError("Set exactly one bot token source")
        if token_file:
            try:
                token = Path(token_file).read_text().strip()
            except OSError:
                raise ValueError("Cannot read bot token file") from None
        chat = env.get("TELEGRAM_CHAT_ID", "").strip().strip('"').strip("'")
        thread = env.get("TELEGRAM_THREAD_ID", "").strip().strip('"').strip("'")
        if not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,100}", token):
            raise ValueError("Invalid bot token configuration")
        if not re.fullmatch(r"-?[0-9]{1,20}", chat) or int(chat) == 0 or not re.fullmatch(r"[0-9]{1,12}", thread) or int(thread) <= 0:
            raise ValueError("Explicit numeric Telegram chat and positive topic ID required")
        polling_enabled = env.get("GOLDSHIELD_TELEGRAM_POLLING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        return cls(token, chat, int(thread), timeout, polling_enabled=polling_enabled)

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

    def get_updates(self, offset=None, timeout=0):
        # One poller per bot token: shared Hermes tokens must remain send-only.
        if not self.polling_enabled or not hasattr(self, "_token"):
            return []
        import urllib.request
        url = "https://api.telegram.org/bot" + self._token + "/getUpdates"
        params = {"timeout": timeout, "limit": 10}
        if offset is not None:
            params["offset"] = offset
        req = urllib.request.Request(
            url,
            data=json.dumps(params).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with self.open_request(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read(65537))
            if data.get("ok") is True:
                return data.get("result", [])
        except Exception:
            pass
        return []


def handle_interactive_command(text, source_dir, state, sender):
    cmd = text.strip().split()[0].lower() if text.strip() else ""
    if "@" in cmd:
        cmd = cmd.split("@")[0]

    source = Path(source_dir)
    if cmd == "/status":
        acc_file = source / "account_live.csv"
        balance = equity = 0.0
        currency = "USD"
        open_pos = 0
        if acc_file.exists():
            try:
                lines = acc_file.read_text(errors="ignore").strip().splitlines()
                if len(lines) >= 2:
                    parts = lines[1].split(",")
                    balance = float(parts[1])
                    equity = float(parts[2])
                    currency = parts[3]
                    open_pos = int(parts[4])
            except Exception:
                pass

        snapshots = sorted(source.glob("demo20_*.csv"))
        snap_data = None
        for p in snapshots:
            val = snapshot_data(p)
            if val and (snap_data is None or val.get("closed_positions", 0) >= snap_data.get("closed_positions", 0)):
                snap_data = val

        is_paused = (source / "MANUAL_PAUSE").exists()
        status_robot = "⏸️ DIJEDA MANUAL (Order baru diblokir)" if is_paused else "🟢 AKTIF NORMAL (Memantau pasar)"

        floating = equity - balance
        float_sign = "+" if floating >= 0 else ""
        float_str = f"{float_sign}{floating:.2f} {currency}" if balance > 0 else "0.00 USD"

        symbol = snap_data.get("symbol", "BTCUSDm") if snap_data else "BTCUSDm"
        closed = snap_data.get("closed_positions", 0) if snap_data else 0
        wins = snap_data.get("wins", 0) if snap_data else 0
        losses = snap_data.get("losses", 0) if snap_data else 0
        winrate = (wins / closed * 100.0) if closed > 0 else 0.0
        net_closed = float(snap_data.get("net_closed", 0.0)) if snap_data else 0.0
        net_sign = "+" if net_closed >= 0 else ""
        quota = f"{snap_data.get('entry_submissions', 0)}/{snap_data.get('limit', 20)}" if snap_data else "0/20"

        msg = (
            "📊 STATUS LIVE ROBOT GOLDSHIELD\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"• Status: {status_robot}\n"
            f"• Simbol: {symbol} (Timeframe M15)\n"
            f"• Saldo: ${balance:,.2f} {currency}\n"
            f"• Ekuitas: ${equity:,.2f} {currency}\n"
            f"• Floating P/L: {float_str}\n"
            f"• Posisi Terbuka: {open_pos} Transaksi\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📈 Hasil Trading Hari Ini:\n"
            f"• Selesai: {closed} (Menang: {wins}, Kalah: {losses})\n"
            f"• Winrate: {winrate:.1f}%\n"
            f"• Profit Bersih: {net_sign}{net_closed:.2f} {currency}\n"
            f"• Kuota Uji DEMO: {quota} Transaksi\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Ketik /recap untuk laporan lengkap atau /help untuk bantuan."
        )
        sender(msg)
        return True

    elif cmd == "/recap":
        recap_msg = generate_daily_recap(source)
        if recap_msg:
            sender(recap_msg)
        else:
            sender("ℹ️ Belum ada data rekapitulasi transaksi hari ini.")
        return True

    elif cmd == "/pause":
        pause_file = source / "MANUAL_PAUSE"
        pause_file.write_text("PAUSED")
        msg = (
            "⏸️ ROBOT BERHASIL DIJEDA\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• Mode: Jeda Manual Aktif\n"
            "• Pembukaan Posisi Baru: DINONAKTIFKAN\n"
            "• Posisi Berjalan: Tetap dilindungi Stop Loss (2.0 ATR), Take Profit, & Trailing Stop hingga selesai.\n"
            "• Untuk mengaktifkan kembali, kirim /resume"
        )
        sender(msg)
        return True

    elif cmd == "/resume":
        pause_file = source / "MANUAL_PAUSE"
        if pause_file.exists():
            try:
                pause_file.unlink()
            except OSError:
                pass
        msg = (
            "▶️ ROBOT KEMBALI AKTIF\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• Mode: Normal\n"
            "• Pembukaan Posisi Baru: DIAKTIFKAN\n"
            "• Robot kembali aktif memantau sinyal entry M15 sesuai aturan filter."
        )
        sender(msg)
        return True

    elif cmd == "/help":
        msg = (
            "🤖 PANDUAN PERINTAH BOT GOLDSHIELD\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• /status - Cek kondisi robot, saldo, ekuitas, dan posisi aktif saat ini\n"
            "• /recap - Lihat ringkasan performa trading harian (Winrate, PnL, dll)\n"
            "• /pause - Jeda pembukaan order baru secara aman (posisi aktif tetap terjaga SL/TP)\n"
            "• /resume - Aktifkan kembali robot untuk mencari peluang entri baru\n"
            "• /help - Menampilkan panduan bantuan ini"
        )
        sender(msg)
        return True

    return False


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

        from datetime import datetime, timezone
        today_date = datetime.now(timezone.utc).strftime("%Y.%m.%d")
        last_recap = self.state.get("last_daily_recap")
        if last_recap is None:
            self.state["last_daily_recap"] = today_date
            self.save()
        elif last_recap != today_date:
            recap_msg = generate_daily_recap(self.source, target_date=last_recap)
            if recap_msg:
                self.state["pending"] = {"message": recap_msg, "group": "system", "key": "daily_recap", "value": today_date}
                self.save()
                self.deliver_pending()
            self.state["last_daily_recap"] = today_date
            self.save()

        # Paket D: Floating Drawdown Alert
        acc_file = self.source / "account_live.csv"
        if acc_file.exists():
            try:
                lines = acc_file.read_text(errors="ignore").strip().splitlines()
                if len(lines) >= 2:
                    parts = lines[1].split(",")
                    bal_val, eq_val, curr, open_cnt = (
                        float(parts[1]), float(parts[2]), parts[3], int(parts[4])
                    )
                    drawdown = max(0.0, bal_val - eq_val)
                    drawdown_pct = (drawdown / bal_val * 100.0) if bal_val > 0 else 0.0
                    last_alert_tier = float(self.state.get("last_drawdown_alert_tier", 0.0))
                    # Trigger alert if floating minus >= 1.0 USD and drawdown_pct >= 0.1%
                    if open_cnt > 0 and drawdown >= 1.0 and drawdown_pct >= 0.1:
                        current_tier = round(drawdown_pct * 4) / 4.0  # Alert every 0.25% step
                        if current_tier > last_alert_tier:
                            alert_msg = (
                                f"⚠️ SIAGA FLOATING DRAWDOWN\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"• Saldo Akun: ${bal_val:,.2f} {curr}\n"
                                f"• Ekuitas Akun: ${eq_val:,.2f} {curr}\n"
                                f"• Floating Minus: -${drawdown:.2f} {curr} (-{drawdown_pct:.2f}%)\n"
                                f"• Posisi Terbuka: {open_cnt} Transaksi\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"🛡️ Proteksi: Robot memantau Stop Loss (2.0 ATR) & Early Cut-Loss otomatis."
                            )
                            self.state["last_drawdown_alert_tier"] = current_tier
                            self.state["pending"] = {"message": alert_msg, "group": "system", "key": "drawdown_alert", "value": current_tier}
                            self.save()
                            self.deliver_pending()
                    elif open_cnt == 0 or drawdown < 0.2:
                        if last_alert_tier > 0.0:
                            self.state["last_drawdown_alert_tier"] = 0.0
                            self.save()
            except Exception:
                pass

        # Interactive polling is opt-in and requires a dedicated, non-Hermes bot.
        if getattr(self.sender, "polling_enabled", False) and hasattr(self.sender, "get_updates"):
            try:
                offset = self.state.get("telegram_update_offset") if self.state else None
                updates = self.sender.get_updates(offset=offset, timeout=0)
                if offset is None and updates:
                    self.state["telegram_update_offset"] = updates[-1]["update_id"] + 1
                    self.save()
                elif updates:
                    for upd in updates:
                        upd_id = upd.get("update_id")
                        if upd_id is not None:
                            self.state["telegram_update_offset"] = upd_id + 1
                            self.save()
                        msg_obj = upd.get("message", {})
                        chat_id = str(msg_obj.get("chat", {}).get("id", ""))
                        if chat_id != str(getattr(self.sender, "chat_id", "")):
                            continue
                        text = msg_obj.get("text", "")
                        if text and text.startswith("/"):
                            handle_interactive_command(text, self.source, self.state, self.sender)
            except Exception:
                pass

    def deliver_pending(self):
        pending = self.state.get("pending") if self.state else None
        if pending and self.state:
            self.sender(pending["message"])
            group = pending.get("group")
            if group and group in self.state and isinstance(self.state[group], dict):
                self.state[group][pending["key"]] = pending["value"]
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
    parser.add_argument("--daily-recap", action="store_true", help="Send daily recap summary to Telegram")
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
        if args.daily_recap:
            recap_msg = generate_daily_recap(source)
            if not recap_msg:
                print("No snapshot data available for daily recap", file=sys.stderr)
                return 1
            ack = sender(recap_msg)
            if not args.dry_run:
                print(json.dumps(ack, sort_keys=True))
            return 0
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
