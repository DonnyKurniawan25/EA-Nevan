# Panduan memasang GoldShield DEMO20 di server Linux

**Ini panduan pemasangan mandiri beserta contoh konfigurasi, belum merupakan instalasi yang sudah diuji pada server Anda.** Tidak ada paket yang dipasang di server. Upaya SSH sebelumnya mengalami timeout. Setelah Anda meminta panduan saja, tidak ada percobaan akses server lanjutan.

Target panduan: **Ubuntu 24.04 x86_64**, user biasa dengan akses sudo, satu MT5 khusus untuk robot ini. Sistem dan kapasitas server Anda belum diverifikasi. Jika server berbeda, sesuaikan setelah memeriksa tahap 1. Akun yang dipakai tetap **DEMO Exness yang sama**, bukan real Cent.

## Gambaran singkat

Server menjalankan **MT5 melalui Wine**, kemudian EA membaca harga dari broker dan memeriksa candle M15 yang selesai. Entry otomatis hanya terjadi jika aturan sinyal dan seluruh pemeriksaan risiko lolos. Cara menjalankan MT5 di Linux memakai Wine dijelaskan oleh [MetaTrader](https://www.metatrader5.com/en/terminal/help/start_advanced/install_linux).

Desktop server dilihat dari PC memakai TigerVNC melalui koneksi SSH. Setelah selesai pemasangan, layanan systemd menjaga prosesnya berjalan saat koneksi SSH/VNC ditutup. **Server tetap harus hidup, terhubung internet dan terhubung ke broker.** Harga baru tersedia ketika market/broker memberikan kuotasi.

Server tidak membuat robot menjadi lebih akurat. Versi ini menggunakan aturan indikator EMA/RSI/ATR, bukan model AI yang sudah terbukti menguntungkan. Filter kalender berita otomatis belum tersedia. Pengaman yang menolak entry tetap berlaku walaupun server online.

Panduan ini memindahkan sesi **XAUUSDm M15**, maksimal **20 pengiriman entry**, maksimal **0,01 lot**, satu posisi, maksimal tiga entry per hari. EURUSD/USDJPY dari analisis sebelumnya belum diaktifkan. Algoritma dan rencana real Cent US$10 tetap dipertahankan.

## 1. Periksa server dahulu — jalankan sendiri melalui SSH

Gunakan koneksi SSH yang biasa Anda pakai. Dalam contoh berikut **SERVER_ANDA** berarti alias SSH atau `user@alamat-server` milik Anda. Tidak ada kata sandi atau private key yang perlu dikirim ke chat.

Di server, jalankan:

```bash
uname -m
cat /etc/os-release
free -h
df -h /
```

Lanjutkan contoh ini jika arsitekturnya **x86_64**, sistemnya Ubuntu 24.04, dan tersedia ruang untuk desktop/Wine/MT5. Untuk perencanaan satu terminal plus desktop, alokasi **2 vCPU, RAM sekitar 4 GB, dan ruang kosong 10 GB atau lebih** merupakan titik awal praktis; pemakaian sebenarnya harus diukur. Ini bukan spesifikasi minimum resmi atau jaminan kecukupan.

Jika hasilnya `aarch64`/ARM, jangan meneruskan perintah contoh ini. Jika server sudah penuh atau menjalankan aplikasi penting lain, tentukan alokasi dan waktu pemasangannya dahulu. Panduan tidak memformat disk atau menghapus aplikasi yang ada.

## 2. Ambil paket dari GitHub atau salin ZIP

Cara GitHub: ikuti [panduan clone](https://github.com/DonnyKurniawan25/EA-Nevan/blob/main/docs/GITHUB_SERVER.md). Alat persiapan menyalin paket ke folder baru `~/goldshield-linux`. Sesudah clone/persiapan, lewati unggah dan ekstrak ZIP di bawah, tetapi tetap pasang paket desktop pada blok apt.

Alternatif ZIP: paket disediakan di desktop PC: **GOLDSHIELD-PANDUAN-LINUX.zip**. Isinya panduan, contoh layanan, robot demo yang sama, dan preset. Tidak berisi password, private key, atau salinan login MT5. Data penghitung aktif belum dibundel karena harus diambil setelah MT5 PC benar-benar dihentikan pada tahap 7.

Di **PowerShell PC**, ganti `SERVER_ANDA` lalu jalankan:

```powershell
$goldZip = Join-Path ([Environment]::GetFolderPath('Desktop')) 'GOLDSHIELD-PANDUAN-LINUX.zip'
scp "$goldZip" SERVER_ANDA:~/
```

Di **SSH server**, sebagai user biasa:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends xfce4 xfce4-terminal dbus-x11 tigervnc-standalone-server tigervnc-tools x11-utils xterm wget unzip python3 procps
mkdir -p "$HOME/goldshield-linux"
unzip -n "$HOME/GOLDSHIELD-PANDUAN-LINUX.zip" -d "$HOME/goldshield-linux"
chmod +x "$HOME/goldshield-linux/runtime/start-mt5.sh" "$HOME/goldshield-linux/runtime/vnc-xstartup"
```

Gunakan direktori baru khusus ini. Jika `~/goldshield-linux` sudah berisi instalasi bot lama, jangan mencampur keduanya atau menimpa state yang sudah ada.

## 3. Buat desktop server yang tetap hidup

Di **SSH server**:

```bash
mkdir -p "$HOME/.vnc" "$HOME/.config/systemd/user"
tigervncpasswd
tigervncserver -list
```

Masukkan password VNC pilihan Anda secara langsung saat diminta. Pilih **No** untuk password view-only jika tidak dibutuhkan. Password VNC ini untuk membuka desktop, berbeda dari password trading.

Contoh konfigurasi memakai display **:1** dan port lokal **5901**. Jika display itu sudah dipakai, sesuaikan konfigurasi dengan pendamping teknis; jangan menghentikan desktop yang tidak terkait.

```bash
cp "$HOME/goldshield-linux/runtime/goldshield-desktop.service" "$HOME/.config/systemd/user/"
cp "$HOME/goldshield-linux/runtime/goldshield-mt5.service" "$HOME/.config/systemd/user/"
sudo loginctl enable-linger "$(id -un)"
systemctl --user daemon-reload
systemctl --user enable --now goldshield-desktop.service
systemctl --user status goldshield-desktop.service --no-pager
ss -ltn '( sport = :5901 )'
```

Status desktop harus `active (running)`. Port 5901 harus mendengarkan di loopback (`127.0.0.1`/`::1`), bukan alamat publik. **Tidak perlu membuka port VNC ke internet.** Template memakai opsi localhost dari [TigerVNC di Ubuntu](https://manpages.ubuntu.com/manpages/noble/man1/tigervncserver.1.html).

`enable-linger` membuat layanan milik user dapat hidup setelah logout dan saat boot; lihat [dokumentasi systemd](https://www.freedesktop.org/software/systemd/man/latest/loginctl.html). Layanan MT5 belum diaktifkan pada tahap ini.

## 4. Buka tampilan server dari PC

Pasang aplikasi **TigerVNC Viewer untuk Windows** dari [situs resmi TigerVNC](https://tigervnc.org/). Yang dibutuhkan di PC adalah Viewer, bukan VNC Server.

Di **PowerShell PC**, buka tunnel:

```powershell
ssh -N -L 127.0.0.1:5901:127.0.0.1:5901 SERVER_ANDA
```

Biarkan jendela ini terbuka selama ingin melihat desktop server. Buka TigerVNC Viewer dan hubungkan ke **127.0.0.1::5901**, lalu masukkan password VNC yang dibuat pada tahap 3. Dua tanda titik dua menunjukkan nomor port.

Sekarang Anda seharusnya melihat desktop Linux. Jangan klik **Log Out** di desktop tersebut ketika ingin meninggalkannya; cukup tutup Viewer. Menutup Viewer/tunnel nanti tidak sama dengan mematikan layanan server.

## 5. Pasang MT5 melalui Wine

Di **SSH server**, unduh skrip installer yang ditautkan dokumentasi resmi MetaTrader. Baca terlebih dahulu, lalu jalankan sebagai user biasa, tanpa menambahkan `sudo` di depan skrip:

```bash
wget -O "$HOME/goldshield-linux/mt5linux.sh" https://download.terminal.free/cdn/web/metaquotes.software.corp/mt5/mt5linux.sh
less "$HOME/goldshield-linux/mt5linux.sh"
DISPLAY=:1 bash "$HOME/goldshield-linux/mt5linux.sh"
```

Tekan `q` untuk keluar dari pembaca teks `less`. Jika installer meminta izin administrasi, ketik password Linux sendiri. Ikuti wizard MT5 pada desktop VNC. Jika installer meminta restart, lakukan ketika sesuai dengan jadwal server Anda, lalu sambungkan SSH/VNC lagi.

Jika MT5 langsung terbuka setelah instalasi, tutup lewat **File → Exit**. Panduan memakai mode **portable** agar lokasi berkas jelas dan tidak tercampur dengan terminal lain. Folder bawaan Wine biasanya `~/.mt5`; contoh `runtime.env` menunjuk ke lokasi itu. Jika lokasi instalasi berbeda, edit berkas `~/goldshield-linux/runtime.env` sesuai lokasi sebenarnya.

Periksa dan mulai mode persiapan:

```bash
source "$HOME/goldshield-linux/runtime.env"
test -f "$GOLDSHIELD_MT5_EXE" && echo 'Lokasi MT5 ditemukan'
"$HOME/goldshield-linux/runtime/start-mt5.sh" setup
```

Tampilan MT5 muncul di VNC. **Login sendiri ke akun DEMO Exness yang sama**, server **Exness-MT5Trial7**. Pilih penyimpanan password di MT5 hanya jika Anda memang ingin terminal server bisa tersambung kembali saat restart. Tidak perlu menaruh password dalam skrip atau file konfigurasi contoh.

Pastikan tertulis **Demo Account**. Mode persiapan menonaktifkan EA dan transaksi otomatis. Setelah login benar, pilih **File → Open Data Folder**: dalam mode portable, folder ini harus sama dengan folder tempat `terminal64.exe` yang dipakai. Bila berbeda, hentikan proses dan perbaiki lokasi/mode dahulu. Akhiri lewat **File → Exit**.

## 6. Jangan menjalankan robot yang sama di dua tempat

Sesudah server siap dipakai, robot di PC harus dihentikan sebelum sesi server diaktifkan. Penghitung dan kunci instance saat ini tersimpan pada masing-masing terminal; kunci itu **tidak menjadi kunci bersama lintas PC/server**. Menjalankan keduanya dapat menggandakan entry dan merusak batas keseluruhan 20 percobaan.

Lakukan perpindahan saat tab **Trade kosong**, tanpa posisi atau pending order pada akun. Jika masih ada posisi, tunggu penanganannya selesai dahulu. Jangan menutup MT5 dengan mengira posisi otomatis ikut ditutup.

## 7. Bekukan dan ekspor sesi dari PC

Di **MT5 PC**, sebelum menutupnya:

1. Pastikan akun DEMO yang sama dan tab Trade kosong.
2. Catat/foto penghitung `UJI DEMO`, jumlah selesai, serta nilai `.d20.used` dan `.reference` pada **Tools → Global Variables / F3** untuk prefix **prefix GS2 yang tercantum di panel sesi Anda**. Cukup lihat; jangan edit atau hapus nilainya.
3. Matikan **Algo Trading**, kemudian pilih **File → Exit** dan pastikan MT5 tertutup.

Pada PC, salin **migration-settings.example.json** menjadi **migration-settings.local.json** di folder paket. Isi lokasi dari MT5 → File → Open Data Folder, MagicNumber dari preset sesi, dan audit_key/prefix GS2 dari panel. Berkas lokal ini tidak ikut Git. Lalu buka berkas pendamping **EXPORT_DEMO20_STATE.ps1** dengan editor teks, baca, lalu jalankan isinya sendiri di PowerShell. Jika menyalin isi ke konsol, masuk dahulu ke folder paket linux-guide agar pengaturan lokal ditemukan. Bila kebijakan Windows memblokir pelaksanaan file skrip, Anda bisa menyalin isinya ke PowerShell; tidak perlu mengubah pengaturan keamanan Windows.

Skrip tersebut hanya bekerja jika proses MT5 sudah tertutup. Ia membuat folder baru **DEMO20-STATE-tanggal-jam** di desktop, menyalin `bases/gvariables.dat` dan berkas pencatatan sesi, memeriksa sidik berkas, lalu mengubah **opt-in preset DEMO20 lokal menjadi OFF** agar pintasan lama tidak langsung mengirim entry lagi. Algoritma dan preset Cent tidak diubah. Skrip ini **belum dijalankan oleh saya**.

`gvariables.dat` menyimpan variabel terminal, termasuk penghitung, rujukan risiko, candle yang sudah diproses, dan status pengaman; lihat [struktur berkas MetaTrader](https://www.metatrader5.com/en/terminal/help/start_advanced/structure). Menyalin file robot saja tidak cukup untuk mempertahankan sesi.

Jika ekspor memberi pesan gagal, berhenti di tahap ini. Jangan membuat ulang angka penghitung dari nol.

## 8. Salin dan impor sesi beku ke server

Di **PowerShell PC**, ganti nama folder di bawah dengan nama yang dihasilkan ekspor:

```powershell
$goldState = Join-Path ([Environment]::GetFolderPath('Desktop')) 'DEMO20-STATE-tanggal-jam'
scp -r "$goldState" SERVER_ANDA:~/
```

Di **SSH server**, pastikan MT5 server masih tertutup, lalu ganti nama folder pada argumen terakhir:

```bash
source "$HOME/goldshield-linux/runtime.env"
python3 "$HOME/goldshield-linux/runtime/import-frozen-state.py" "$HOME/DEMO20-STATE-tanggal-jam"
```

Pengimpor ini diperuntukkan bagi terminal baru yang khusus untuk sesi ini. Ia memverifikasi identitas sesi dan sidik berkas, mencadangkan file variabel tujuan jika ada, memasang binary/preset, dan menyalin state asli. Ia menolak terminal yang sudah memiliki penanda sesi ini dan menolak impor ulang ke sesi yang sudah diaktifkan. Jangan gunakan untuk menimpa terminal trading lain.

Pesan berhasil berarti penyalinan terverifikasi, **belum berarti trading diaktifkan**. Data state ini bukan file publik; simpan untuk penggunaan pribadi. Tidak perlu menyalin folder login/password MT5 dari PC.

## 9. Periksa tanpa entry dahulu

Di **SSH server**:

```bash
"$HOME/goldshield-linux/runtime/start-mt5.sh" stage
```

Lihat MT5 lewat VNC. Cocokkan:

- Akun DEMO yang sama, server Exness-MT5Trial7, simbol **XAUUSDm M15**.
- Nama robot **GoldShield_DEMO20** dan prefix **prefix GS2 yang tercantum di panel sesi Anda**.
- Penghitung `.d20.used` pada F3 dan rujukan `.reference` **sama persis** dengan catatan PC; penghitung tidak turun atau kembali ke nol.
- Batas `.d20.limit` tetap **20**. Jumlah posisi tetap nol.
- Tidak ada `ERROR_BLOCKED`, state hilang, atau perubahan konfigurasi yang belum diperiksa.

Preset STAGE memakai `EnableAutoTrading=false`, `DemoTradingOptIn=false`, dan izin transaksi terminal OFF. Karena itu belum membuka posisi. Periksa pula izin **Allow Algo Trading** per robot di F7 → Common; untuk tahap aktif nanti izin ini diperlukan bersama pengaturan lainnya.

Jika angka berbeda, akun berbeda, prefix berubah, atau bot menampilkan error, jangan lanjut mengaktifkan. Jangan menghapus variabel untuk melewati pesan. Tutup MT5 melalui **File → Exit** setelah pemeriksaan selesai.

## 10. Aktifkan demo di server dan autostart

Lakukan hanya setelah tahap 9 cocok dan robot PC tetap OFF. Di **SSH server**:

```bash
touch "$HOME/goldshield-linux/ACTIVATE_DEMO20"
systemctl --user enable --now goldshield-mt5.service
systemctl --user status goldshield-mt5.service --no-pager
journalctl --user -u goldshield-mt5.service -n 40 --no-pager
```

Lewat VNC pastikan robot muncul, Algo Trading aktif, dan angka sesi sesuai. Lihat tab **Experts/Journal** serta koneksi broker. `active (running)` pada layanan hanya menunjukkan proses berjalan; tidak menjamin robot sudah berhasil masuk akun atau lolos inisialisasi.

Konfigurasi aktif memuat preset sesi yang sama, bukan mengubah aturan sinyal untuk memaksa entry. Robot tetap menunggu candle baru. Setelah 20 pengiriman entry, entry baru berhenti dan posisi terakhir tetap dikelola. Gagal setelah pengiriman tetap memakai satu jatah; jumlah posisi terisi bisa kurang dari 20.

Layanan mencoba menjalankan kembali MT5 jika prosesnya keluar. Jika gagal berulang, systemd membatasi percobaan; periksa log, perbaiki penyebab, baru gunakan `systemctl --user reset-failed goldshield-mt5.service` dan mulai ulang. Jangan menghapus state trading untuk mengatasi kegagalan proses.

## 11. Uji bahwa PC sudah boleh dimatikan

1. Catat waktu harga/pesan terbaru di MT5 server.
2. Tutup VNC Viewer dan tunnel SSH di PC, tanpa Log Out desktop Linux.
3. Sambungkan kembali setelah beberapa menit. Saat pasar aktif, pastikan harga atau catatan evaluasi berikutnya bertambah dan sesi tetap sama.
4. Uji restart server terjadwal saat akun flat dan sesuai jadwal aplikasi lain yang mungkin berjalan di sana. Setelah boot, periksa kedua layanan, koneksi akun, panel robot, dan penghitung.

Baru setelah pemeriksaan ini berhasil, anggap pengaturan autostart terverifikasi pada server tersebut. Reboot yang berhasil memulai proses belum cukup bila MT5 meminta login manual lagi.

## 12. Memantau dan menjeda

Untuk melihat proses lewat SSH:

```bash
systemctl --user status goldshield-desktop.service goldshield-mt5.service --no-pager
journalctl --user -u goldshield-mt5.service -n 40 --no-pager
```

Untuk hasil trading, gunakan **panel UJI DEMO**, tab **Trade**, dan **History** pada MT5 server. Anda juga bisa login akun demo di MT5 HP untuk melihat posisi/riwayat; EA tetap berjalan pada server. Jangan memasang salinan EA aktif lain di PC.

Untuk menjeda entry sambil melihat posisi, matikan **Algo Trading pada MT5 server melalui VNC**. Mematikan Algo Trading pada PC **tidak menghentikan robot server**. Izin yang dimatikan juga mencegah perintah EA untuk mengubah/menutup posisi; SL/TP yang sudah di server broker tetap berlaku.

Untuk berhenti menjalankan proses server dan menonaktifkan autostart MT5:

```bash
systemctl --user disable --now goldshield-mt5.service
```

Ini **tidak menutup posisi trading**. Periksa posisi terlebih dahulu. Untuk perawatan, gunakan perintah penghentian layanan sebelum menutup MT5; jika layanan masih aktif, MT5 yang ditutup dapat dijalankan lagi otomatis.

Jangan menyalakan kembali opt-in robot PC saat server aktif. Jika ingin berpindah kembali ke PC, lakukan alur pemindahan state terbaru dari server setelah layanan dihentikan dan akun flat; jangan memakai snapshot PC lama karena bisa menurunkan penghitung atau mereset pengaman.

## Bila ada kendala

| Kendala | Yang diperiksa |
| --- | --- |
| SSH timeout | Server hidup, alamat/port benar, dan aturan akses dari penyedia server. Jangan lanjut menganggap instalasi berhasil. |
| Desktop kosong / layanan VNC gagal | `journalctl --user -u goldshield-desktop.service -n 40 --no-pager`, display :1 belum dipakai, password VNC sudah dibuat. |
| `terminal64.exe` tidak ditemukan | Lokasi yang sebenarnya dan isi `runtime.env`. Jangan menyalin path contoh sebagai fakta bila installer berbeda. |
| MT5 meminta login setelah restart | Masuk sendiri ke demo yang sama dan periksa penyimpanan login; jangan aktifkan akun real. |
| `HOLD_RULES_NO_SETUP` | Robot menunggu syarat sinyal; bukan kegagalan server. |
| `MINIMUM_LOT_EXCEEDS_RISK_OR_VOLUME_BUDGET` | Kebutuhan risiko lot minimum lebih besar dari sisa anggaran; server tidak menghilangkan pengaman ini. |
| Counter/prefix berubah setelah migrasi | Hentikan tahap aktif dan periksa impor state/akun. Jangan membuat state baru untuk melewati masalah. |
| Layanan aktif tetapi keputusan tidak bertambah | Periksa koneksi broker, jam pasar, panel, dan Experts/Journal; layanan hanya memantau proses. |

Tidak ada konfigurasi ini yang mengaktifkan akun real. Build EA ini menolak akun real. Jika kelak Anda memberi instruksi baru untuk real Cent US$10, spesifikasi akun dan kelayakan strategi tetap perlu diperiksa terpisah.
