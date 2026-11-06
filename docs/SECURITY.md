# Keamanan Phase 1

- Tidak ada login/password MT5, API key, token Telegram, credential broker atau data identitas yang diminta/disimpan pada source/preset.
- Tidak ada HTTP, DLL, service Python atau eksekutor kedua. Semua request trading berada dalam `OrderExecutor.mqh` dan dibatasi demo.
- Audit runtime memuat ticket/deal/position identifier dan informasi harga/risiko; perlakukan sebagai data privat. Account login/server dipakai hanya untuk derivasi hash scope storage dan tidak ditulis sebagai identitas polos dalam file log. Hash bukan anonymization kuat.
- `.set` pada fase berikutnya dapat berisi secret bila desain berubah; jangan commit atau membagikannya. Saat ini tidak ada secret input.
- Global Variables, CSV dan sentinel file lokal tidak memiliki autentikasi atau integritas kriptografis. Batasi akses Windows/VPS; jangan memodifikasi F3/state saat EA aktif.
- Tidak ada remote PAUSE/CLOSE/RESUME, dashboard trading atau auto-withdraw. Mode/fitur belum tersedia ditolak saat init.
- Installer memeriksa seluruh target sebelum copy dan tidak menimpa file existing yang berbeda; tidak menyalakan terminal atau Algo Trading.

Backend/Telegram/ONNX mendatang memerlukan review masing-masing setelah gate core lulus; keberadaan dokumen ini bukan bukti security testing layanan yang belum dibuat.
