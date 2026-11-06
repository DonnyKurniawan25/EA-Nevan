# Arsitektur core Phase 1

```text
OnTick ──┐
         ├─ GSProcess (single event cycle)
OnTimer ─┘    ├─ identitas akun + konektivitas
              ├─ broker position/order reconciliation
              ├─ persistent intent confirmation / residual exit check
              ├─ basic equity/margin/position risk exit (priority)
              ├─ persistent latch / cooldown / active-position gates
              ├─ fresh tick + new closed bar (OnTick only)
              ├─ EMA/RSI/ATR RULES candidate or HOLD
              ├─ risk sizing + symbol/session/account checks
              └─ OrderCheck → durable intent → CTrade → reconcile later

OnTradeTransaction → short audit event only; no trade submission
```

`SHADOW` dan `DRY_RUN` menghitung kandidat tanpa trade request, termasuk tanpa close/modification. `RULES_DEMO` hanya dapat mengelola posisi jika `DemoTradingOptIn=true` dan akun demo hedging serta izin terminal valid. Entry memerlukan `EnableAutoTrading=true` juga. Mematikan entry pada mode demo yang sudah opt-in tetap membolehkan pengaman close posisi EA; mengganti ke SHADOW menghentikan semua request trading dan menyisakan stop broker serta monitoring.

State yang digunakan: `INIT → RECOVERY → READY → SIGNAL_PENDING → OPENING → BASKET_ACTIVE → BASKET_EXITING → COOLDOWN`. Jalur HOLD/pause menggunakan `SAFE_MODE`, `PAUSED_MANUAL`, `PAUSED_VOLATILITY`, `PAUSED_RISK`, `ERROR_BLOCKED`. Alasan setiap perubahan ditulis ke CSV dan Journal. Ini state mesin core single-position; belum memiliki lifecycle bounded-grid.

## Identitas, storage, idempotency

- Scope ownership: account/server terminal aktif + simbol persis + magic + prefix comment `GS2|<candle server epoch>` + ticket/position identifier broker.
- Scope lock: hash server/account/symbol/magic, tidak mencakup timeframe sehingga dua chart dengan timeframe berbeda tidak mengeksekusi identitas yang sama.
- File lock tanpa share flag di `MQL5/Files/GoldShield/` menolak instance kedua pada terminal yang sama. Belum ada koordinasi lintas terminal/VPS.
- Global Variables menyimpan bar yang sudah dikonsumsi, pending intent, risk latch, equity reference, cooldown dan hitungan retry close. Nilai diflush sebelum send.
- File lock juga berisi sentinel. Jika Global Variables hilang/expired tetapi sentinel masih ada, init ditolak; anchor risiko tidak direset diam-diam.
- Sesudah submit, method return atau retcode tidak cukup untuk menghapus intent. Satu posisi broker dengan comment tepat mengonfirmasi entry. Hasil yang tetap ambigu memerlukan review operator; tidak ada auto retry.
- Close memakai ticket yang dicek ulang, maksimal tiga request persisten per lifecycle, jeda 10 detik, sisa posisi tetap dipantau. Latch risiko tidak auto-resume.

## Batas implementasi

Belum ada model ML, H4/H1 alignment, regime/router, grid, basket-money TP, Telegram, API, news/calendar, trailing/BE atau komponen web. Jangan membangun fitur di atas hasil simulasi seolah telah terverifikasi di broker. Gate berikutnya adalah kompilasi dan smoke test core, baru implementasi Phase 2 lengkap.
