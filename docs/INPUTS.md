# Input Phase 1

Nilai berikut adalah default source, bukan rekomendasi parameter profit. `point` berarti `SYMBOL_POINT` broker, jarak harga berarti harga simbol, lot mengikuti volume broker. Nilai uang selalu **mata uang akun**, termasuk USC jika akun cent.

| Input | Default | Satuan dan alasan / perilaku |
|---|---|---|
| ExecutionMode | SHADOW | Enum; DRY_RUN/SHADOW tidak mengirim request trading. RULES_DEMO hanya demo opt-in |
| EnableAutoTrading | false | Boolean; entry otomatis dimatikan |
| DemoTradingOptIn | false | Boolean; izin eksekusi/manajemen demo harus disengaja |
| AllowRealTrading | false | Boolean reserved; true ditolak, real execution tidak tersedia |
| TradeSymbol | XAUUSD | Nama simbol persis, harus sama dengan chart; suffix tidak ditebak |
| SignalTimeframe | PERIOD_M15 | Harus sama dengan chart; PERIOD_CURRENT ditolak |
| MagicNumber | 26011060 | Identitas EA, bukan password; harus nonzero dan khusus instance ini |
| CapitalLimitUSD | 0.0 | 0=tanpa cap tambahan; profil pemula 10. USD/USC dikonversi eksplisit, ledger tidak direset saat restart |
| RequiredAccountCurrency | kosong | Preset Cent mengharuskan USC; menolak akun USD Standard |
| SignalModel | GS_BASELINE | 0=baseline EMA/RSI; 1=eksperimen H1/pullback yang belum lolos perbandingan |
| TrendTimeframe | PERIOD_H1 | Model 1 saja; timeframe lebih tinggi, candle tertutup |
| MaxEntryStretchATR | 1.0 | Model 1: batas jarak close terhadap EMA cepat, dalam ATR |
| FastEMAPeriod | 20 | Candle; periode EMA cepat untuk baseline |
| SlowEMAPeriod | 50 | Candle; lebih besar dari fast |
| RSIPeriod | 14 | Candle; periode RSI |
| UseRSIFilter | true | Boolean; BUY RSI 50–70, SELL 30–50 |
| ATRPeriod | 14 | Candle; periode ATR |
| MinClosedBars | 250 | Candle; warmup/kelengkapan data, tidak menggunakan bar berjalan |
| StopATRMultiple | 2.0 | Kali ATR; SL juga melewati high/low candle setup dan minimum broker |
| RewardRiskMultiple | 2.0 | Rasio jarak target terhadap jarak stop awal; bukan expected payoff empiris |
| MaxCandleATRMultiple | 3.0 | Kali ATR; range candle lebih besar menghasilkan HOLD |
| MaxGapATRMultiple | 1.0 | Kali ATR; batas gap candle dan deviasi bid dari close sinyal |
| MaxSignalAgeSeconds | 120 | Detik sejak waktu penutupan candle server; sinyal lama ditolak |
| BaseLot | 0.01 | Lot maksimum permintaan; ukuran turun jika budget risiko lebih kecil |
| MaxRiskPerTradePct | 0.5 | % equity; source Phase 1 menolak >0.5 |
| MaxAggregateOpenRiskPct | 1.0 | % equity; estimated remaining risk semua posisi akun + usulan; source menolak >1.0 |
| MaxTotalAccountLots | 0.10 | Jumlah lot mentah seluruh akun; cap tambahan, bukan penyetaraan notional |
| MaxAccountPositions | 3 | Posisi semua akun sebelum entry; EA sendiri tetap maksimal satu posisi |
| MinMarginLevelPct | 500.0 | % equity/margin; memeriksa margin saat ini dan proyeksi |
| MinFreeMarginPct | 50.0 | % equity yang perlu tersisa sebagai free margin setelah order |
| RiskBufferPct | 25.0 | % tambahan pada estimasi kerugian ke SL untuk ketidakpastian biaya/slippage |
| CostBufferPerLot | 10.0 | Mata uang akun per lot; contoh buffer biaya, wajib kalibrasi broker |
| EquityShieldMinPctOfReference | 90.0 | % equity reference saat state dibuat; trigger latch permanen bila equity <= ambang |
| MaxPositionLossPct | 2.0 | % equity reference; floating profit+swap EA di bawah batas memicu latch/close yang tersedia |
| MaxAllowedSpreadPoints | 100 | Point broker; contoh semata, tidak berlaku seragam pada 2/3 digit gold |
| StaleTickSeconds | 15 | Detik server; batas usia quote |
| MaxDeviationPoints | 20 | Point; permintaan deviasi CTrade, bukan jaminan slippage maksimum |
| CooldownMinutes | 30 | Menit setelah posisi terpantau selesai |
| SessionStartHourServer | 0 | Jam server broker inklusif; bukan WITA/WIB |
| SessionEndHourServer | 24 | Jam server eksklusif; interval overnight input belum didukung |
| MaxDailyLossPct | 0.5 | Batas realized trading loss akun per hari server terhadap reference; preset PC 0.03 |
| MaxWeeklyLossPct | 1.0 | Batas realized trading loss per pekan mulai Senin; preset PC 0.075 |
| MaxConsecutiveLossesPerDay | 2 | Dua posisi EA tertutup rugi setelah biaya memblokir entry sampai hari broker berikutnya |
| MaxEntriesPerDay | 3 | Posisi baru EA per hari; partial fills tidak dihitung ganda |
| GridEnabled | false | Boolean; true ditolak karena Phase 6 belum dibuat |
| ApiEnabled | false | Boolean; true ditolak karena Phase 5 belum dibuat |
| TelegramEnabled | false | Boolean; true ditolak karena modul belum dibuat |
| EnableChartPanel | true | Boolean; panel `Comment()` menampilkan status/limit sebenarnya |
| ExportResearchBars | false | Ekspor lokal candle tertutup hanya dalam Strategy Tester; bukan izin trading atau upload |

Mode enum numerik pada `.set`: DRY_RUN=0, SHADOW=1, RULES_DEMO=2, ONNX_DEMO=3, HYBRID_DEMO=4, REAL_RESTRICTED=5. Tiga mode terakhir ditolak pada Phase 1.

Lot minimum yang melewati budget menghasilkan HOLD; tidak pernah otomatis dinaikkan ke minimum. Bila akun memakai USC, default biaya 10 USC/lot berbeda secara nominal dari 10 USD/lot; metadata kontrak dan evaluasi exposure tetap harus diperiksa. Tidak ada preset konversi angka saldo cent menjadi saldo Standard.
