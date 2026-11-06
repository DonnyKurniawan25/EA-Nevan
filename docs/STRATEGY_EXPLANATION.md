# Strategi baseline Phase 1

Pada tick pertama candle baru, EA mengambil EMA20, EMA50, RSI14 dan ATR14 pada **shift 1**. BUY kandidat bila close > EMA20 > EMA50 dan RSI 50–70. SELL kandidat bila close < EMA20 < EMA50 dan RSI 30–50. RSI dapat dimatikan. HOLD berlaku bila arah tidak jelas atau filter data/spread/volatilitas/gap menolak.

Baseline default tetap satu timeframe. Eksperimen SignalModel=1 menambahkan H1 EMA alignment, slope EMA M15, pullback candle sebelumnya yang diikuti breakout tertutup dan stretch maksimal 1 ATR. H1 harus tertutup dan tersedia pada waktu keputusan M15. Hasil September/Oktober masih merugi, sehingga eksperimen tidak dipilih sebagai default. Belum ada H4, range reversal, model prediktif atau skor probabilitas. Candle baru setelah attach tetap diperlukan. Lihat reports/IMPROVEMENT_RESULTS.md.

SL BUY berada di bawah entry minus ATR multiplier, low candle setup dan batas jarak broker, lalu dibulatkan turun ke tick size. SL SELL berlaku simetris ke atas. Target dihitung dari jarak SL aktual × `RewardRiskMultiple`, dibulatkan menjauh dari entry. SL/TP adalah server-side dalam request pembukaan awal. Tidak ada grid, trailing, BE, averaging atau pelebaran stop.

Volume dibatasi BaseLot, sisa cap lot, risiko per entry/aggregate serta sisa budget loss harian, mingguan dan equity shield. OrderCalcProfit menghitung kerugian ke SL, ditambah buffer, lalu volume dibulatkan turun. Bila minimum lot tidak memenuhi budget, tidak ada transaksi. Limit history direkonstruksi sebelum entry sehingga restart tidak menghapus kerugian/streak hari berjalan.

Sinyal kandidat belum tentu menjadi order: mode, opt-in, akun, simbol, sesi, spread, margin, exposure, ownership, cooldown, intent persisten dan `OrderCheck` masih dapat menolak. Tidak ada bukti profitabilitas strategi ini dalam implementasi yang diserahkan.
