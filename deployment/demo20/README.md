# Uji 20 entry pada harga pasar DEMO

Diotorisasi pengguna pada 6 November 2026: memakai saldo virtual demo Standard yang tersedia, maksimal 0,01 lot, akun real Cent US$10 tidak digunakan. Aturan sinyal dan pengaman adalah salinan terisolasi dari build 1.201; file algoritma utama dan preset Cent tidak diubah.

`GoldShield_DEMO20` menolak akun real, server selain Exness-MT5Trial7, dan currency selain USD. Batas total **20 pengiriman entry** disimpan ke disk sebelum permintaan broker. Penolakan setelah pengiriman tetap memakai satu slot; tidak ada retry entry yang hasilnya ambigu. Entry ke-21 ditolak. Posisi terakhir tetap dikelola sampai selesai, dengan SL/TP server. Restart tidak mengatur ulang penghitung.

Uji berjalan pada XAUUSDm M15 dan hanya membuka entry ketika aturan serta risk preflight lolos. Maksimal tiga entry per hari dan jeda setelah dua kerugian beruntun mengikuti preset demo yang sudah ada. Jadi 20 transaksi membutuhkan sedikitnya tujuh hari perdagangan, bisa lebih lama atau berhenti lebih awal karena pengaman. Tidak ada pemaksaan 20 buy/sell sekaligus.

Pintasan desktop: **GOLDSHIELD - DEMO 20 TRANSAKSI**. Jika MT5 tertutup, buka pintasan yang sama agar counter/magic sesi tetap sama. PC, internet dan MT5 harus tetap aktif. Mematikan Algo Trading menjeda izin transaksi EA; SL/TP server tetap ada pada posisi yang sudah terbuka.

Status langsung ditulis di folder data MT5 → `MQL5/Files/GoldShield/demo20_<magic>.csv` dan panel chart. Nomor magic serta lokasi status tersimpan pada `reports/demo20_session.json`. Jangan menghapus Global Variables atau mengganti magic untuk mereset percobaan.

Validasi sebelum aktivasi: kompilasi 0 error/0 warning, 48 pemeriksaan counter/persistensi lulus tanpa order, serta sandbox historis menghasilkan tepat 20 posisi tertutup dan berhenti menambah entry. Sandbox itu bukan bagian dari 20 transaksi demo harga sekarang.

Kegiatan ini menguji baseline RULES yang sudah ada. Model lokal AI tetap belum disetujui sebagai pengambil keputusan order. Hasil uji tidak menjamin profit.
