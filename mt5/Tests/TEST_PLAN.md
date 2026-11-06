# Gate Phase 1 dan rencana pengujian MT5

**C01 dan U01 LULUS** pada 6 November 2026: MetaEditor 6302, EA dan script unit 0 error/0 warning; script MQL berjalan langsung di MT5 dengan 1.023 checks dan 0 failures. S01 diperiksa pada XAUUSDm M15 demo hedging: SHADOW/READY, tidak ada posisi/pending order. Percobaan input XAUUSD pada chart XAUUSDm juga ditolak sesuai pengaman S04. Lihat `reports/mt5_compile.json` dan `reports/mt5_runtime.json`. Skenario lain belum dinyatakan lulus hanya dari hasil native/source statis.

| ID | Tindakan / kondisi | Ekspektasi |
|---|---|---|
| C01 | Compile EA dan script tes pada MetaEditor | 0 error; seluruh warning ditinjau dan log disimpan |
| U01 | Jalankan script `GoldShield_SafetyMath_Tests` | 1.023 checks, 0 failures; tidak ada order |
| S01 | Pasang default SHADOW pada XAUUSD M15 demo hedging | Panel terisi; tidak ada request order/close/modify |
| S02 | Tunggu candle baru dengan kandidat BUY/SELL | Sinyal dicatat, tidak ada order pada SHADOW |
| S03 | Attach/restart di tengah candle | Tidak mengeksekusi candle historis saat attach |
| S04 | Simbol input XAUUSD tetapi chart XAUUSDc | Init ditolak, tidak pindah simbol diam-diam |
| S05 | Timeframe input berbeda chart atau PERIOD_CURRENT | Init ditolak |
| S06 | Akun netting | Init ditolak dengan pesan hedging required |
| S07 | RULES_DEMO pada real / AllowRealTrading=true | Ditolak; tidak ada order real |
| S08 | EnableAutoTrading=false atau DemoTradingOptIn=false | Tidak ada entry; SHADOW/DRY_RUN tidak ada request apa pun |
| S09 | Grid/API/Telegram diaktifkan, atau ONNX/HYBRID/REAL mode dipilih | Init ditolak sebagai fitur belum tersedia |
| S10 | Dua chart dengan simbol/magic sama dalam terminal | Instance kedua gagal mengambil lock |
| S11 | Bar/tick/indicator belum siap atau signal lama | HOLD/SAFE_MODE; tidak ada entry |
| S12 | Spread lebar, candle >ATR limit atau gap besar | HOLD; monitoring posisi tidak berhenti |
| S13 | Matikan terminal setelah intent, lalu restart | Tidak retry entry yang ambigu; broker direkonsiliasi dahulu |
| S14 | Event callback ganda/berbeda urutan | Tidak menambah posisi karena callback |
| S15 | File log/state tak dapat ditulis | Entry diblokir; exit dasar tetap dicoba jika ownership jelas dan mode mengizinkan |
| S16 | Global Variables hilang tetapi sentinel ada | Init ditolak, anchor/latch tidak direset otomatis |

## Pengujian executor pada lingkungan demo terkontrol

Jalankan hanya setelah C01/U01/S01–S16 lulus dan sebagai pengembangan validasi, bukan forward trading bebas. Gunakan akun demo terpisah; tidak mengubah akun real.

| ID | Kondisi | Ekspektasi |
|---|---|---|
| E01 | RULES_DEMO, kedua toggle true, akun hedging demo, satu sinyal valid | Maksimal satu posisi, SL/TP server terpasang, filled ticket/volume diverifikasi |
| E02 | Min lot melebihi budget | HOLD, tidak memaksa min lot |
| E03 | Tick size 0.05 / digit 2 dan digit 3 | Harga stop mengikuti tick, lot mengikuti step |
| E04 | Posisi manual simbol sama atau magic lain | Tidak ditutup/dimodifikasi EA; risiko akun tetap dihitung |
| E05 | Posisi manual tanpa SL / pending order akun / exposure cap | Entry ditolak |
| E06 | OrderCalcProfit/Margin/OrderCheck error | Tidak mengirim order |
| E07 | Requote/reject/timeout setelah intent | Tidak entry retry; log hasil, tahan intent untuk review |
| E08 | Partial fill/residual position | Volume/ticket aktual diverifikasi; tidak menambah volume untuk mengejar request |
| E09 | Equity/margin/SL/floating loss emergency | Latch tersimpan; close hanya ticket EA, max 3 tries, 10 s backoff, residual tetap ditampilkan |
| E10 | Emergency dalam SHADOW/DRY_RUN | Alert/latch monitoring, tidak ada request close; verifikasi pengaman broker |
| E11 | Broker mengubah comment / magic collision / posisi EA ganda | Block review, tidak memodifikasi ownership ambigu |
| E12 | Restart setelah fatal latch | Tidak auto-resume meski API/koneksi/equity pulih |
| E13 | Akun demo USC vs USD | Nilai uang/margin sesuai currency/contract metadata; tidak mengasumsikan exposure sama |

## Strategy Tester

Gunakan real ticks bila tersedia, spread/komisi/swap broker serta periode beragam. `OnTimer`/`OnTick` tidak memanggil HTTP. SHADOW untuk smoke tanpa order; executor test demo memerlukan toggle sengaja dan account mode yang dilaporkan tester harus DEMO hedging, kalau tidak source menolak. TimeGMT tidak dilabeli UTC historis pada tester.

Laporan harus memuat rentang data, broker/simbol, biaya, mode, parameter, error/reject, drawdown, exposure/margin, order tanpa SL (target 0), duplicate order (target 0), worst trade dan residual setelah emergency. Simpan report MT5 asli; belum ada report performa dalam proyek ini.

Phase 2 menambahkan daily/weekly loss, cashflow/history recovery, loss streak dan fault injection menyeluruh. Phase 3–8 tetap menunggu gate core/risk sesuai spesifikasi.
