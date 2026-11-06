# GitHub → clone → persiapan server

Repositori: **https://github.com/DonnyKurniawan25/EA-Nevan**. Repositori ini publik saat diperiksa. Kode dan template boleh diambil dari Git; akun trading, password, kunci SSH, serta state aktif tidak boleh dimasukkan ke repositori.

## 1. Clone sendiri di server

Pada contoh Ubuntu/Debian, pasang Git jika belum ada:

```bash
sudo apt-get update
sudo apt-get install -y git python3
git clone https://github.com/DonnyKurniawan25/EA-Nevan.git "$HOME/EA-Nevan"
cd "$HOME/EA-Nevan"
python3 tools/prepare_linux_runtime.py --destination "$HOME/goldshield-linux"
```

Gunakan folder tujuan baru. Alat persiapan menolak menimpa runtime yang sudah ada, memverifikasi sidik berkas yang dibundel, lalu menyalin file yang tercantum saja. Tidak ada akses broker, instalasi sistem, atau aktivasi trading pada perintah ini.

Repositori publik dapat di-clone melalui HTTPS tanpa password GitHub untuk membaca kode. Jika kelak diubah menjadi Private, siapkan autentikasi sendiri; salah satu pilihan untuk satu repo pada server adalah **deploy key read-only**. Private key tetap di server, public key ditambahkan ke pengaturan repo. Jangan memasukkan private key/token ke Git atau URL yang disimpan. Sumber: [clone GitHub](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository), [deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys).

## 2. Lanjutkan pemasangan MT5

Buka [panduan Linux](../deployment/linux-guide/PANDUAN_SERVER_LINUX.md). Paket sudah berada di `~/goldshield-linux`; lewati unggah/ekstrak ZIP, tetapi tetap lakukan pemasangan paket desktop, Wine/MT5, serta seluruh tahap pemeriksaan lainnya. Contoh konfigurasi ditujukan untuk Ubuntu 24.04 x86_64; server tujuan belum diverifikasi.

Login sendiri ke **DEMO Exness yang sama**. Saat siap berpindah, hentikan terminal PC saat akun flat, ekspor state terpisah, lalu impor dan periksa penghitung dengan entry OFF. Setelah angkanya cocok dan robot PC OFF, lanjutkan aktivasi demo server.

Untuk ekspor dari PC, salin `migration-settings.example.json` menjadi `migration-settings.local.json`, lalu isi lokasi data terminal, magic, dan audit key dari sesi Anda. Berkas lokal tersebut diabaikan Git. Password tidak diperlukan dalam berkas ini.

## 3. Bedakan update market dengan update kode

**Harga market diterima MT5 dari broker ketika terminal terhubung.** Anda tidak perlu `git pull` untuk memperbarui harga. Git dipakai untuk mengambil perubahan kode/konfigurasi yang sudah ditinjau.

Untuk memperbarui salinan source:

```bash
cd "$HOME/EA-Nevan"
git status --short
git pull --ff-only
```

Runtime berada di folder terpisah `~/goldshield-linux`. Karena itu pull tidak langsung mengganti robot yang sedang berjalan. Sebelum memasang versi baru, tunggu akun flat, hentikan layanan, cadangkan state terbaru, periksa perubahan dan rencanakan pemasangannya. Jangan menjadwalkan pull/restart otomatis yang mengganti logika saat posisi terbuka.

## 4. Memperbarui kode dari PC

Gunakan root repo lokal `goldshield-ai-v2`, bukan folder data MT5. Setelah mengubah source dan menjalankan pemeriksaan:

```powershell
git status --short
git add -- NAMA_FILE_YANG_DIUBAH
git diff --cached --stat
git commit -m "Jelaskan perubahan"
git push origin main
```

Tinjau file yang akan dikirim. Jangan memaksa penambahan `reports`, screenshot, database login, `gvariables.dat`, `DEMO20-STATE-*`, `ACTIVATE_DEMO20`, atau pengaturan pribadi. [Aturan ignore GitHub](https://docs.github.com/en/get-started/git-basics/ignoring-files).

Repositori tetap **DEMO ONLY**. Akun real Cent US$10 tidak diaktifkan. Clone tidak memasang robot secara otomatis dan tidak membawa penghitung/state aktif. Tidak ada langkah panduan ini yang dijalankan pada server oleh asisten.
