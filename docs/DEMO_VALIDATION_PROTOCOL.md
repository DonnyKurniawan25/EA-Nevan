# Protokol evaluasi dan pengembangan EA DEMO

## Tujuan dan batas

Permintaan operator: menguji dan mengembangkan EA di akun DEMO sebelum mempertimbangkan penggunaan real. Dokumen ini menetapkan prosedur evaluasi, bukan klaim hasil, jaminan profit atau sertifikasi layak real. Jangan mengaktifkan akun real secara otomatis.

Source yang diperiksa memakai aturan indikator `GSEvaluateRules` / EMA-RSI dan filter risiko. Eksekusi DEMO yang terkumpul tidak dengan sendirinya melatih bobot ML atau mengubah strategi. Istilah training pada tahap ini berarti pengumpulan data nyata, evaluasi dan eksperimen parameter yang terkontrol.

## Gate0 — kebenaran status operasional

- Bedakan login MT5, sesi EA terinisialisasi, izin transaksi, koneksi broker, serta fill/order yang benar-benar dikonfirmasi broker.
- Jangan menyebut robot aktif hanya karena proses MT5 atau web console berjalan.
- Sesi server baru menggunakan Magic/namespace terpisah, bukan impor palsu atau reset state PC. PC EA harus tetap dinonaktifkan.
- Inisialisasi STAGE memasang EA dengan izin trading OFF; tahap ini membuat state, jadi bukan pengamatan tanpa perubahan state. Hanya native account probe yang read-only.
- Aktifkan sesi DEMO hanya setelah mode akun asli, broker, koneksi, izin, posisi/pending kosong dan state asli yang dibuat EA lolos pemeriksaan.

## Gate1 — baseline dibekukan

- Pertahankan source/binary/preset risiko semula dan catat commit, hash binary, preset, Magic, simbol/timeframe serta waktu mulai.
- Batas saat ini tetap maksimum0.01lot, satu posisi, tiga entry/hari dan20 pengiriman entry per sesi. Kegagalan pengiriman tetap menghabiskan slot sebagaimana implementasi asli.
- Jangan memaksa sinyal, menghapus latch, memperbesar risiko, memperlonggar filter atau mengulang sesi otomatis agar grafik terlihat bagus.
- Sesi20 percobaan dipakai sebagai pilot fungsi dan keselamatan, bukan bukti statistik yang otomatis cukup untuk real. Jangan diam-diam memperpanjang atau mereset cap untuk mengumpulkan sampel lebih besar.

## Gate2 — data aktual dan rekonsiliasi

- Simpan audit sinyal, alasan HOLD/penolakan, intent, request, callback, broker fill dan penutupan dengan identitas sesi yang konsisten.
- Pisahkan order intent/request, pengiriman gagal, posisi terisi dan posisi tertutup. Callback sukses sendiri bukan bukti posisi terisi.
- Ambil hasil transaksi dari riwayat broker yang direkonsiliasi per position/deal, termasuk komisi, swap dan biaya. Snapshot `net_closed` DEMO20 adalah agregat; jangan mengarang P/L per trade dari perubahan snapshot yang mungkin melompati beberapa penutupan.
- Kurangi/mask nomor akun, jangan simpan password, OTP, bot token, link console atau credential dalam laporan/Git.
- Jika belum ada trade, metrik kinerja diberi label BELUM ADA DATA / TIDAK DAPAT DINILAI, bukan akurasi0/100 atau profit simulasi yang disajikan sebagai aktual.

## Gate3 — evaluasi multi-metrik

Protokol tidak menerima persentase menang sebagai satu-satunya tolok ukur. Laporan akan menyertakan jumlah sampel/periode, win rate, rata-rata hasil bersih per posisi, profit factor, drawdown balance dan equity, kerugian beruntun, eksposur serta biaya eksekusi. MetaTrader menyediakan profit factor, expected payoff dan statistik drawdown sebagai ukuran yang berbeda pada laporan tester.[2]

- Nyatakan metrik yang tidak dapat dihitung: misalnya rasio dengan denominator kosong dan statistik dengan sampel terlalu sedikit.
- Pisahkan hasil backtest, forward DEMO dan riwayat transaksi aktual akun; jangan menggabungkan jenis hasil tersebut menjadi satu angka akurasi.
- Tetapkan toleransi risiko/kriteria eksperimen sebelum membuka hasil holdout; target belum ditentukan tidak boleh diganti diam-diam setelah melihat hasil.

## Gate4 — eksperimen yang dapat direproduksi

- Versi baseline tetap dipertahankan. Uji perubahan kecil yang disebutkan eksplisit pada konfigurasi riset terisolasi; jangan mengoptimasi langsung pada terminal DEMO yang sedang mengelola posisi.
- Pisahkan periode pencarian parameter dari periode pengujian yang tidak dipakai memilih parameter. Forward testing MT5 menjalankan hasil optimasi pada periode berbeda untuk memeriksa kecocokan berlebihan terhadap data historis.[1]
- Bekukan konfigurasi sebelum forward DEMO berikutnya; catat perubahan yang diuji dan semua hasil, termasuk eksperimen yang gagal.
- Catat sumber/kualitas data, rentang waktu, spread, komisi, swap, slippage/delay dan asumsi eksekusi. Jangan memperbaiki performa laporan dengan meniadakan biaya atau memilih periode terbaik saja.
- Jangan menjalankan cloud optimization berbayar, polling model terus-menerus atau kampanye DEMO baru tanpa persetujuan ruang lingkupnya.

## Gate5 — keputusan tetap berhati-hati

Hasil hipotetis mempunyai keterbatasan dan tidak mewakili trading aktual; NFA secara khusus menyoroti hindsight, likuiditas, slippage dan perbedaan dampak risiko finansial.[3] Karena itu hasil backtest/DEMO tidak dipromosikan sebagai jaminan hasil real.

Laporan akhir harus menyebut data yang tersedia, hasil sesungguhnya, ketidakpastian, risiko, kegagalan eksekusi dan apa yang belum diuji. Hasil tidak memadai berarti lanjut evaluasi atau menolak strategi, bukan menaikkan risiko demi mengejar akurasi. Akun real tidak diaktifkan oleh alur ini.

## Sources

[1] https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization
    > "Forward testing is the repeated run of the best optimization results on a different time period."
[2] https://www.metatrader5.com/en/terminal/help/algotrading/testing_report
    > "Profit Factor — ratio of the gross profit to the gross loss."
[3] https://www.nfa.futures.org/rulebook/rules.aspx?RuleID=9025&Section=9
    > "hypothetical performance results do not represent actual trading"
