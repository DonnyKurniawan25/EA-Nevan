# Deployment server — GoldShield DEMO20

Verifikasi awal: 6 November 2026 (UTC). Ini status bootstrap server, bukan bukti strategi menguntungkan atau acceptance trading.

## Yang sudah dijalankan

- Repository di `/home/ubuntu/EA-Nevan`; runtime hasil verifikasi manifest di `/home/ubuntu/goldshield-linux`.
- Ubuntu 24.04 x86_64; WineHQ staging 11.21; terminal MT5 x64 build 6305.
- MT5 dijalankan sebagai user `ubuntu`, prefix `/home/ubuntu/.mt5`, mode `/portable`.
- Desktop privat TigerVNC `:1` hanya mendengarkan `127.0.0.1:5901` dan `[::1]:5901` dengan VNC authentication. Tidak ada port VNC publik yang dibuka.
- `goldshield-desktop.service` milik user `ubuntu` aktif dan enabled; linger aktif.
- `goldshield-mt5-setup.service` aktif hanya untuk login/setup. Start config `SETUP.ini`: Experts OFF, AllowLiveTrading OFF, DLL OFF. Layanan setup belum enabled saat boot.
- Layanan `goldshield-mt5.service` untuk sesi aktif tetap disabled. File `ACTIVATE_DEMO20` dan receipt impor belum dibuat.
- Binary DEMO20 dan dua preset disalin ke folder MT5 dengan hash sama persis dengan manifest. Tidak ada algoritma atau preset trading yang diubah.
- Tes Python baseline: 21 kasus ditemukan, 18 lulus, 3 installer Windows dilewati di Linux. Tes matematika C++ memakai `.mqh` asli: 40.055 assertions lulus. Ini bukan uji fill/disconnect broker atau backtest profitabilitas.
- Layanan yang sudah ada tidak dihentikan untuk deployment. Container tetap Up; pemeriksaan HTTPS Nevstore dan Boost menghasilkan HTTP 200 setelah bootstrap.

## Belum diverifikasi / penghalang aktivasi

1. Login ke akun DEMO Exness yang benar, dilakukan operator secara privat. Tidak ada password broker dalam Git atau template runtime.
2. Sesi di PC harus flat, Algo Trading OFF, MT5 ditutup. Snapshot asli `DEMO20-STATE-...` harus diekspor sesuai panduan, bukan membuat ulang counter.
3. Impor snapshot dan cocokkan prefix, reference, used counter, limit 20, akun, simbol, dan posisi pada STAGE.
4. Baru setelah pemeriksaan operator lengkap, aktivasi demo dan layanan autostart trading boleh dilakukan. Tidak pernah memakai akun real.
5. Belum ada uji order broker di server, restart broker/disconnect, atau reboot host. Jangan menganggap layanan proses aktif sebagai EA siap trading.

## Notifikasi dan verifikasi tambahan

- Observer Telegram terpisah dipasang sebagai sistem service `goldshield-notifier.service`, user `ubuntu`, writable hanya `/var/lib/goldshield-notifier`; kredensial tetap di luar Git dan tidak dicetak.
- Unit enabled tetapi **sengaja inactive** karena receipt state PC belum ada. Pemeriksaan `ConditionResult=no` terkonfirmasi. Setelah impor/STAGE, mulai observer untuk baseline sebelum aktivasi demo; jangan membuat receipt palsu.
- Self-test nyata berlabel BUKAN TRANSAKSI diterima di topik yang ditentukan operator. Exact target chat/thread/message diperiksa kembali. Ini tes transport, bukan bukti order broker.
- Suite final: 36 kasus Python ditemukan; 3 installer Windows dilewati. Seluruh kasus yang dijalankan lulus, termasuk 15 kasus notifier. Regression mencakup anti-spam saat history unavailable, Bahasa Indonesia, dan kewajiban ACK chat/topic yang benar.
- Tidak ada akun demo/login, frozen state, atau order broker yang diuji. Trading tetap OFF dan algoritme/binary/preset tetap identik.

## Akses desktop dari PC operator

Password VNC awal dibuat acak di server dan tidak dikirim ke chat. Operator menetapkan password sendiri melalui SSH:

```bash
sudo -u ubuntu tigervncpasswd
```

Perubahan password perlu dimuat ulang oleh desktop. Koordinasikan dengan pendamping operator untuk me-restart **hanya layanan desktop dan setup GoldShield** selagi belum ada trading/posisi. Jangan mematikan desktop trading aktif untuk mengganti password tanpa pemeriksaan posisi dan jadwal.

Buka tunnel SSH dari PC, ganti `SERVER_ANDA` dengan host SSH yang biasa dipakai:

```powershell
ssh -N -L 127.0.0.1:5901:127.0.0.1:5901 SERVER_ANDA
```

TigerVNC Viewer: `127.0.0.1::5901`. Login broker dilakukan langsung pada MT5 server; tidak melalui grup Telegram. Menutup Viewer/tunnel bukan logout desktop.

## Perintah status melalui SSH root

```bash
sudo -u ubuntu env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user status goldshield-desktop.service goldshield-mt5-setup.service goldshield-mt5.service --no-pager
```

Panduan migrasi lengkap tetap `deployment/linux-guide/PANDUAN_SERVER_LINUX.md`. Jangan melewati alur impor hanya karena binary sudah dipasang. Notifikasi eksternal didokumentasikan terpisah; `TelegramEnabled` di EA tidak diaktifkan.
