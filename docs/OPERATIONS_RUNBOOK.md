# Operasi, pause, restart dan pemulihan

## Awal / monitoring

Pasang SHADOW pada akun demo hedging, cocokkan symbol/timeframe, periksa panel dan Journal. `READY` berarti core siap menunggu candle, **bukan** lulus kompilasi/backtest/approval demo. CSV berada di `MQL5/Files/GoldShield/`; simpan salinannya untuk evaluasi.

## Pause entry

Dalam RULES_DEMO yang sudah opt-in, set `EnableAutoTrading=false` untuk memblokir entry baru sambil mempertahankan upaya exit dasar. Mengganti ke SHADOW/DRY_RUN atau mematikan Algo Trading memblokir **seluruh** request trading lokal; jangan mengandalkannya untuk emergency close. SL/TP broker tetap tersimpan pada posisi yang sudah mendapat konfirmasi.

## Emergency close

Tidak ada tombol/remote close pada Phase 1. Bila latch risiko aktif, EA mencoba close ticket miliknya pada mode demo opt-in, maksimal tiga request, interval minimal 10 detik. Periksa residual position di terminal. Jika terminal/broker tidak tersedia, gunakan prosedur resmi broker. Jangan menutup posisi manual/magic lain atas nama EA.

## Restart / disconnect

Saat restart, EA mengunci scope instance, membaca state dan posisi/order broker sebelum sinyal. Intent positif yang tidak dapat dipastikan tidak diulang. Posisi tunggal dengan comment request persis dapat mengonfirmasi intent. Signal saat attach diabaikan sampai candle berikutnya. Saat disconnect, panel menunjukkan `SERVER_STOPS_ONLY`; tidak menganggap exit virtual masih bekerja.

Jika broker mengubah comment atau ada lebih dari satu posisi EA, status menjadi blocked untuk review. Jangan menghapus latch untuk “mencoba lagi” sebelum seluruh order/deal/residual diperiksa.

## Review latch/state secara manual

Belum ada reset otomatis atau tool reset pada Phase 1. Setelah **memastikan tidak ada order/posisi ambigu**, simpan CSV, Journal, screenshot posisi serta Global Variables (F3). Nonaktifkan EA, periksa `GS2.<hash>` yang ditampilkan panel. Pengubahan `.pending`, `.blocked`, `.reference`, cooldown atau sentinel hanya dilakukan sebagai bagian review teknis dengan keputusan operator; kesalahan reset dapat menghilangkan pengaman. Tidak ada prosedur “hapus semua Global Variables”.

Sentinel dengan Global Variables yang hilang/expired menyebabkan init ditolak. Pulihkan backup yang konsisten atau lakukan investigasi sebelum membuat state baru. Gate recovery lengkap Phase 2 belum lulus.

## Uninstall

Pause entry, periksa/manage posisi demo yang masih terbuka, lepaskan EA dari chart. Deinit tidak otomatis menutup posisi. Cadangkan source/log/state lalu hapus hanya file proyek jika diperlukan. Jangan menghapus Standard Library atau file posisi manual. Tidak ada service/backend terpasang oleh proyek ini.

## VPS

Gunakan Windows untuk MT5. Jaga clock PC, koneksi dan akses OS; timer EA bukan watchdog eksternal. Periksa stop broker pada setiap posisi. Jangan menjalankan scope account/server/symbol/magic yang sama pada terminal lain; lock saat ini hanya satu terminal. Panduan monitoring dan backup production lengkap termasuk Phase 8, belum diverifikasi di sini.
