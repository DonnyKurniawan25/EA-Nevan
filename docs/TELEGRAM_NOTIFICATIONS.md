# GoldShield: notifikasi Telegram read-only

Observer Python standard-library terpisah dari MT5. Tidak mengubah EA/binary/algoritme, tidak memanggil terminal/trade API, tidak menerima perintah Telegram dan tidak menjalankan `getUpdates`. **Core `TelegramEnabled` harus tetap `false`.** Perintah manusia kelak lewat topik Hermes adalah integrasi terpisah, bukan fitur notifier ini.

## Sumber yang benar

Arahkan `GOLDSHIELD_FILES_DIR` ke direktori **terminal DEMO yang aktif**, `MQL5/Files/GoldShield`, bukan Journal/Experts log, report tester, atau direktori source repository. EA dapat mempunyai beberapa terminal/Wine prefix; konfirmasi file berubah pada terminal yang benar.

* `deployment/demo20/Include/GoldShieldDemo20/Metrics.mqh` menulis ANSI CSV `GS2.<16-hex>.csv`, header:
  `event_id,server_time,utc_time,clock_source,event,symbol,candle_id_server,reason_code,details`.
  `server_time` adalah waktu broker, bukan otomatis UTC; tester dapat tidak mempunyai `utc_time`.
* `OrderExecutor.mqh`: `ORDER_INTENT` adalah intent sebelum reserve/send; `ORDER_RESULT` adalah hasil request, **bukan fill** walau method true/retcode DONE. `GoldShield_DEMO20.mq5` menghasilkan `FILL_CONFIRMED` setelah broker position reconciliation. `CLOSE_RESULT` juga request saja; `EXIT_CONFIRMED`/`POSITION_CLOSED` menunjukkan posisi tidak lagi ada, tanpa menghitung profit.
* `DemoTrial.mqh::GSDemo20Status` melakukan **truncate + rewrite**, bukan append, untuk `demo20_<magic>.csv`:
  `time_server,account_mode,symbol,limit,entry_submissions,filled_positions,closed_positions,wins,losses,net_closed,currency,open_positions,trial_status,core_state,core_reason`.
  `entry_submissions` adalah slot submission, bukan jumlah fill. `filled_positions` adalah jumlah position identifier dari history. `closed_positions` hanya posisi yang incoming/outgoing volume-nya sudah seimbang. `net_closed` adalah **agregat kumulatif** closed positions termasuk profit, commission, swap, fee. Notifier tidak membagi agregat atau mengklaim profit satu trade.

Audit penting: intent/result/check, confirmed position, close request/confirmation, storage/init failure, dan safety state. SIGNAL, READY, candle/tick/HOLD rutin diabaikan. Safety state/reason identik terakhir disuppress per audit stream sampai alert berbeda; bukan pengingat berkala. Snapshot mengirim perubahan counter/trial/safety/net. Audit dan snapshot dapat menghasilkan dua konfirmasi terkait; tidak diklaim sebagai dua trade.

## Konfigurasi (operator, jangan masukkan secret ke Git/chat)

Buat `/etc/goldshield/telegram.env`, owner root, mode `0600`; parent directory mode `0700`. Contoh **placeholder, harus diganti operator**:

```ini
TELEGRAM_BOT_TOKEN=REPLACE_WITH_BOT_TOKEN
TELEGRAM_CHAT_ID=REPLACE_WITH_NUMERIC_CHAT_ID
TELEGRAM_THREAD_ID=REPLACE_WITH_POSITIVE_TOPIC_ID
GOLDSHIELD_FILES_DIR="/home/ubuntu/.mt5/drive_c/Program Files/MetaTrader 5/MQL5/Files/GoldShield"
GOLDSHIELD_STATE_DIR=/var/lib/goldshield-notifier
```

Alternatif token: `TELEGRAM_BOT_TOKEN_FILE=/etc/goldshield/bot-token`, file `0600`; hilangkan `TELEGRAM_BOT_TOKEN`. Tepat satu sumber token. Chat ID dan topic ID **wajib eksplisit**; tidak ada destination default, tidak ada topik general fallback. Bot harus mempunyai izin mengirim ke topik tersebut. `--dry-run` tidak memerlukan token/destination dan tidak memakai jaringan.

```sh
# Preview pesan servis, tidak ada jaringan atau fake trade:
/usr/bin/python3 tools/telegram_notifier.py --self-test --dry-run

# Satu scan, hanya preview; state baru tidak dibaseline secara permanen:
/usr/bin/python3 tools/telegram_notifier.py --source-dir /path/to/GoldShield \
  --state-dir /var/lib/goldshield-notifier --once --dry-run

# Dengan environment yang di-load secara aman oleh operator:
/usr/bin/python3 tools/telegram_notifier.py --self-test
/usr/bin/python3 tools/telegram_notifier.py --source-dir /path/to/GoldShield \
  --state-dir /var/lib/goldshield-notifier --once
```

Self-test selalu berlabel `UJI SERVIS — BUKAN TRANSAKSI`, tidak menyintesis order/fill/profit dan tidak mengubah cursor. Pada sukses nyata stdout berisi JSON `message_id`, `chat_id`, `thread_id` untuk readback independen; token tidak dicetak. Jangan menaruh token di argumen command line. Exit: 0 sukses/baseline/preview, 1 delivery tidak terkonfirmasi, 2 konfigurasi/state/input gagal. Default scan 2 detik, HTTP timeout 15 detik; kegagalan delivery diulang dengan backoff maksimum 300 detik.

## Service contoh (belum deployment)

Review `deployment/telegram-notifier/goldshield-notifier.service`, salin ke `/etc/systemd/system/`, lalu operator dapat menjalankan `systemd-analyze verify`, `systemctl daemon-reload`, `systemctl enable --now goldshield-notifier`. Ini **bukan** langkah yang dijalankan oleh unit test.

Service mempunyai `ConditionPathExists=/home/ubuntu/goldshield-linux/state-import-receipt.json`: sebelum impor state PC, proses observer **tidak dijalankan**, agar file history impor tidak dianggap transaksi baru. Setelah impor dan verifikasi STAGE, mulai notifier terlebih dahulu agar baseline history tersimpan, baru aktivasi demo. Jangan hapus receipt/cursor untuk melewati pengaman. Alokasi observer dibatasi RAM 128 MB dan CPU 20%.

Service berjalan sebagai `ubuntu`, menggunakan `/usr/bin/python3 /home/ubuntu/EA-Nevan/tools/telegram_notifier.py`, `ProtectHome=read-only`, `ProtectSystem=strict`, capability kosong, write hanya `/var/lib/goldshield-notifier` (private temporary filesystem systemd tidak dipakai notifier). systemd membaca credential root-only dari `/etc/goldshield/telegram.env` sebelum menurunkan privilege. Path MT5 yang mengandung spasi dipakai langsung dari environment, tanpa shell/splitting. `GOLDSHIELD_STATE_DIR` harus sesuai direktori writable service. Token-file opsional perlu akses baca bagi user service (misalnya root:ubuntu `0640`), bukan file root-only. Tidak ada write ke MT5 atau Wine.

## Delivery, privasi, dan batasan

* **Gate DEMO:** sebelum audit atau pending dikirim, seluruh snapshot terdeteksi harus valid dan `account_mode=DEMO`; snapshot hilang/partial/REAL menahan semua pesan trade tanpa mengubah cursor. Audit tidak mempunyai account_mode, sehingga direktori harus khusus terminal DEMO. Jangan mencampur log real/demo; perpindahan akun wajib review manusia sebelum melanjutkan backlog. Self-test servis tidak memerlukan snapshot. Instalasi saat ini tetap diblokir sampai frozen-state PC dan login DEMO diverifikasi; notifier tidak membuka blokir trading.
* Pertama kali: audit yang sudah ada dibaseline sampai record lengkap terakhir, snapshot existing dijadikan baseline; **tidak ada flood history**. File baru setelah baseline diamati dari awal. Menghapus state menyebabkan baseline ulang dan bisa melewatkan notifikasi, bukan replay history.
* Cursor durable: JSON private, atomic replace + file/directory fsync. Pesan pending dan target cursor dipersist sebelum HTTP; cursor event baru maju setelah acknowledgement `ok=true` dan `message_id`. Restart mengirim pending lebih dahulu, termasuk snapshot yang sumbernya sudah ditimpa. Lock CLI mencegah dua instance live menggunakan state sama.
* Semantik **at-least-once untuk record yang sudah diamati dan tetap tersedia**. Timeout sesudah Telegram menerima pesan atau crash antara acknowledgement dan checkpoint dapat menghasilkan duplikat. Bukan exactly-once. Dry-run tidak mengubah cursor durable.
* Partial record/CSV quoted multiline ditunggu sampai lengkap. Numeric rotated audit `.csv.1`, `.csv.2` ikut dibaca; inode mencegah replay setelah rename, anchor mendeteksi truncate/rewrite. Retain rotated files sampai backlog terkirim. File dihapus sebelum scan, copy-truncate saat unread backlog, inode reuse, atau truncate/regrow dengan prefix/anchor identik tidak dapat dijamin tanpa durable journal dari produser. Copy rotation dapat menduplikasi record.
* Snapshot hanya keadaan terakhir saat scan; perubahan antara scan/selama outage bisa digabung atau terlewat. EA sendiri hanya rewrite saat signature berubah (used, closed, wins, owned count, state/reason); perubahan history/net saja tidak selalu langsung tertulis. Tidak ada rekonstruksi ticket atau profit per-trade. Bila history unavailable/counter reset, perlukan review manusia.
* MT5 text diperlakukan sebagai data tidak tepercaya: tidak ada `parse_mode`, tidak ada raw account logs, semua details selain numeric key whitelist dibuang. Symbol gold dibatasi, unknown reasons disamarkan, pesan maksimal 1500 karakter, preview tautan dimatikan. Ini bukan saluran untuk mengirim login/password/bot token. HTTPS normal certificate verification, redirect tidak diikuti; body/error URL tidak dicetak. State juga hanya menyimpan field terpilih dan pesan tersanitasi.
* ANSI source dibaca sebagai CP1252; bagian yang dikirim sengaja ASCII/whitelist. Tidak ada freshness heartbeat/stale-terminal alarm. Kehilangan koneksi notifier **tidak menghentikan EA** dan tidak mengubah risk guard trading.

## Tes offline

```sh
/home/ubuntu/goldshield-linux/test-venv/bin/python -m unittest discover -s tests -p test_telegram_notifier.py -v
```

Fixture mengikuti schema MQL sebenarnya; sender/HTTP di-inject secara lokal, tanpa Telegram/MT5/broker nyata. Review hasil sebelum deploy dan lakukan service self-test berlabel hanya setelah destination nyata dikonfirmasi operator.
