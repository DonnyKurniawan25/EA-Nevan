# Deployment server — GoldShield DEMO20

Terakhir diverifikasi: **7 November 2026, 03:33 UTC**. Status operasi DEMO, bukan bukti profitabilitas atau kelayakan akun real.

## Jalur yang dipilih operator

Operator membatalkan migrasi PC dan memilih **sesi DEMO baru di server**, setelah menyatakan EA PC dinonaktifkan. Sesi server menggunakan Magic/namespace baru; state lama tidak dihapus atau direset. Receipt impor PC tidak dibuat. Panduan migrasi tetap tersedia untuk migrasi yang memang disetujui, bukan syarat sesi baru ini.

- Repo: `/home/ubuntu/EA-Nevan`.
- Sesi privat: `/home/ubuntu/goldshield-server-demo/server-20261107`.
- MT5 berjalan sebagai `ubuntu`, prefix `/home/ubuntu/.mt5`, `/portable`, display `:1`.
- Akun dipilih lewat konfigurasi privat dari preflight native yang tervalidasi; password tersimpan MT5 tidak diekstrak.

## Bukti operasi aktual

- Native preflight membuktikan koneksi DEMO, USD, hedging, `Exness-MT5Trial7`, `XAUUSDm`, akun flat, history tersedia, Magic belum terpakai dan namespace belum ada **sebelum inisialisasi**.
- STAGE tanpa order membuat reference/counter/schema secara alami lewat EA asli. Native terminal trading flag **0**, kedua schema **1**, counter **0/20**, posisi/order **0/0**, block/pending **0**. Receipt genuine dibuat verifier.
- Setelah shutdown normal STAGE, identitas berkas persisten dan state tetap terjaga. Tidak ada globals, lock, counter atau reference yang direkayasa.
- RUN terpisah `goldshield-server-demo.service` sudah **active/running dan enabled**. Native terminal trading flag **1**; dialog properti EA yang sedang terpasang menunjukkan **Allow Algo Trading dicentang**. Input aktual menunjukkan `EnableAutoTrading=true`, `DemoTradingOptIn=true`, `AllowRealTrading=false`, mode `RULES_DEMO`; properti EA mengonfirmasi `XAUUSDm,M15`.
- Restart aplikasi melalui systemd benar-benar dijalankan. PID berubah; bukti native sesudah restart tetap cocok untuk akun, broker, simbol, Magic, namespace, reference, counter **0/20** dan cap **20**. Device/inode berkas persisten tetap sama; posisi/order tetap **0/0**, block/pending **0**.
- Satu chart pada profil milik sesi; launcher hanya mengarsipkan profil UI milik sesi, tidak menghapus state trading.
- Unit memakai bounded `Restart=always`; desktop user service aktif, linger aktif. Autostart dikonfigurasi; host tidak direboot untuk pengujian.
- Status core terakhir **SAFE_MODE / STALE_TICK_OR_SERVER_CLOCK**. EA aktif tetapi belum mengirim order; perlindungan harga/waktu tidak dilemahkan dan sinyal tidak dipaksakan.

## Batas pilot dan pemantauan

- DEMO saja; hard rejection akun real tetap dipertahankan.
- Lot `0.01`, total lot akun maksimal `0.01`, satu posisi, tiga entry/hari, maksimal **20 entry submissions**. Submission gagal tetap memakai slot; restart tidak mengisi ulang kuota.
- Sumber/algoritme, binary EX5 stok, dan preset dasar tetap identik. Preset turunan privat hanya membedakan identitas sesi dan opt-in tahap STAGE/RUN sesuai guard.
- `goldshield-notifier.service` aktif/enabled; gate memakai receipt STAGE sesi baru, bukan receipt migrasi. Cursor terpisah dibaseline dari audit/snapshot aktual **sebelum** marker aktivasi dibuat. Kredensial Telegram di luar Git.
- Tujuan notifikasi mengikuti grup/topik yang sudah diverifikasi. Self-test transport terdahulu berlabel BUKAN TRANSAKSI; bukan bukti order. Observer tidak mengeksekusi BUY/SELL.
- Banner konsol dan pesan akses bersifat netral terhadap fase: status Algo Trading dilihat di MT5/konfirmasi topik, bukan klaim statis Trading OFF.

## Pengujian dan batas verifikasi

- Suite terbaru: **72 tes Python, OK dengan 3 skip installer Windows**, serta **11 tes UI Node lulus**.
- Safety-math C++ memakai `.mqh` asli: **40.055 assertions lulus**. Ini bukan backtest profitabilitas.
- Observer native dikompilasi dengan MetaEditor aktual: **0 errors, 0 warnings**, EX5 hasil compile benar-benar ada. CLI exit code saja tidak dipakai sebagai bukti.
- Review independen jalur sesi baru, profil, binding akun dan perbaikan global-off STAGE: SPEC PASS lalu kualitas approved.
- **Belum ada order/fill/close broker dari sesi ini**, hasil forward-test bermakna, pengujian disconnect broker, atau reboot host. Uptime dan izin ON tidak membuktikan order sukses atau strategi menguntungkan.
- Evaluasi DEMO mengikuti `docs/DEMO_VALIDATION_PROTOCOL.md`; trading tidak melatih bobot ML otomatis dan 20 submission bukan sertifikasi statistik. Akun real memerlukan keputusan terpisah.

## Perintah status melalui SSH root

```bash
sudo -u ubuntu env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user status goldshield-desktop.service goldshield-server-demo.service --no-pager
systemctl status goldshield-notifier.service --no-pager
```

Untuk maintenance, periksa posisi/order dahulu. Menghentikan Algo Trading juga menghentikan close/modify oleh EA, bukan hanya entry; SL/TP broker tetap berlaku dan menutup MT5 tidak menutup posisi.

Akses HP melalui tombol konsol privat sekali pakai; jangan bagikan link atau kredensial. Menutup browser/HP tidak menghentikan MT5 server. TigerVNC tetap loopback-only; jangan membuka port VNC publik. Password broker hanya diisi operator langsung di MT5, bukan dalam chat atau Git.

Prosedur sesi baru: `docs/NEW_SERVER_DEMO_SESSION.md`. Jalur migrasi lama tetap terpisah di `deployment/linux-guide/PANDUAN_SERVER_LINUX.md`; jangan menggunakannya untuk memalsukan atau mereset sesi baru.
