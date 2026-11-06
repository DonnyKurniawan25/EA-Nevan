# EA-Nevan / GoldShield

Robot MT5 untuk pengujian **DEMO**. Core versi **1.201** dan pembatas sesi DEMO20 versi **1.220** tersedia dalam source. Build ini menolak akun real. Tidak ada klaim profit atau akurasi yang dijamin.

## Clone di server Linux

```bash
git clone https://github.com/DonnyKurniawan25/EA-Nevan.git "$HOME/EA-Nevan"
cd "$HOME/EA-Nevan"
python3 tools/prepare_linux_runtime.py --destination "$HOME/goldshield-linux"
```

Perintah terakhir memeriksa sidik berkas lalu menyalin paket ke **folder baru**. Perintah itu tidak memasang Wine/MT5, melakukan login, memulai layanan, atau mengaktifkan trading. Lanjutkan:

- [Panduan GitHub ke server](docs/GITHUB_SERVER.md).
- [Pemasangan Linux lengkap](deployment/linux-guide/PANDUAN_SERVER_LINUX.md), contoh Ubuntu 24.04 x86_64.
- [Pemasangan source MT5 di Windows](docs/INSTALL.md).

Konfigurasi server belum diuji pada server tujuan. Ikuti persiapan, login sendiri ke demo, pemeriksaan entry OFF, lalu aktivasi dan pengujian autostart.

## Perilaku robot

- EMA20/50, RSI14, ATR14 dari candle tertutup; tidak entry langsung saat attach/restart.
- Pemeriksaan data, spread, lonjakan harga, margin, eksposur akun dan batas kerugian sebelum entry.
- Server-side SL/TP, intent persisten, rekonsiliasi broker, tanpa pengulangan entry yang hasilnya ambigu.
- Core default **SHADOW**, kedua opt-in entry OFF, real diblokir dalam kode.
- Preset khusus DEMO20 mengizinkan demo hanya setelah perpindahan sesi dan aktivasi diverifikasi. Maksimum **20 pengiriman entry**; request gagal setelah dikirim juga memakai jatah.

Sesi demo yang disertakan memakai **XAUUSDm M15**, maksimum **0,01 lot**, satu posisi, maksimal tiga entry sehari, serta jeda/pengaman kerugian. Posisi terakhir tetap dikelola setelah jatah entry habis. Jangan menjalankan sesi yang sama aktif di PC dan server bersamaan.

Model AI lokal masih riset. ONNX, grid, HTTP/API, Telegram, dan filter kalender berita otomatis belum tersedia sebagai fitur trading siap pakai. Server online tidak meningkatkan akurasi strategi dengan sendirinya.

## Data di luar Git

Aturan ignore mengecualikan kunci/password, konfigurasi pribadi, database akun, snapshot penghitung/pengaman, laporan trading, screenshot PC, file aktivasi, backup dan log. **Clone tidak membawa sesi trading aktif.** Penghitung dan reference harus dipindahkan terpisah setelah terminal asal dihentikan dan akun flat; jangan diatur ulang menjadi nol.

`runtime.env` adalah contoh lokasi aplikasi, bukan tempat password. Pengaturan operator memakai `migration-settings.local.json` atau `runtime.local.env` yang tidak dilacak. Jangan memakai `git add -f` untuk berkas pribadi.

## Peta source

| Lokasi | Isi |
| --- | --- |
| `mt5/Experts/`, `mt5/Include/GoldShield/` | Core MQL5 dan pengaman |
| `mt5/Presets/` | Preset pemantauan; template Cent US$10 dengan entry OFF |
| `deployment/demo20/` | Source pembatas sesi 20 entry demo |
| `deployment/linux-guide/` | Panduan, layanan, binary demo, preset dan alat migrasi |
| `tests/` | Pemeriksaan source, installer dan matematika |
| `tools/` | Alat developer; sebagian alat MT5 membutuhkan konteks Windows lokal |
| `SPEC.md` | Spesifikasi yang dipertahankan byte-identik |

Pemeriksaan Python menggunakan Python 3.10+ dan NumPy untuk tes riset lokal:

```bash
python -m unittest discover -s tests -v
```

Kompilasi dan uji MT5 dilakukan terpisah memakai MetaEditor/Strategy Tester. Pemeriksaan source tidak membuktikan strategi menguntungkan atau siap uang real. Bukti pengujian dan laporan akun lokal tidak dipublikasikan.

Lihat [batas implementasi](docs/LIMITATIONS.md), [runbook operasi](docs/OPERATIONS_RUNBOOK.md), dan [rencana uji MT5](mt5/Tests/TEST_PLAN.md).
