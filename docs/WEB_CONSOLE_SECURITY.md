# Private phone desktop console

This component is a loopback-only authenticated VNC transport, not a trading API. It does not read broker credentials, MT5 files, change strategies, enable Algo Trading, or stop the desktop. Interactive desktop access can still operate the existing GUI: it is not a broker-side read-only enforcement mechanism. Trading activation requires separate explicit authorization.

## Interface

- `GET /ea-console/`, `app.js`, `app.css`: public shell only.
- `POST /ea-console/api/session`: exact configured Origin, `X-EA-Console: 1`, JSON containing only `ticket`. Returns `{expires_at}` and `__Secure-goldshield_session`, Secure/HttpOnly/SameSite=Strict, Path=/ea-console/.
- `GET /ea-console/api/session`: authenticated expiry or 401.
- `POST /ea-console/api/connection`: authenticated, exact Origin and `X-EA-Console: 1`; returns `{password,expires_at}`. Password is exclusively the systemd VNC credential, never a broker credential. Frontend must keep it only in memory.
- `POST /ea-console/api/logout`: authenticated, exact Origin and header; revokes and clears cookie.
- `GET /ea-console/ws`: authenticated cookie plus exact Origin. Binary only, fixed 127.0.0.1:5901, no query parameters. Test injection of local port is Python-only, unavailable in CLI/environment/HTTP. Text closes with 1003; frames above 1 MiB are rejected. TCP/WebSocket drain has a 3-second bound. Session revocation/expiry is checked every 250 ms, including idle connections; disconnecting does not stop MT5. A new socket replaces the previous socket for that session.
- `GET /ea-console/vendor/...`: authenticated, confined to the configured noVNC directory; traversal and symlink escape rejected. No directory listings or CORS.

All responses carry no-store, no-referrer, nosniff, frame DENY and restrictive self-only script/style CSP. Request bodies, including chunked GET bodies, are limited to 4 KiB. No analytics or access logging. Reverse proxy must also disable console access logs and must never log query strings, request bodies, cookies, or credentials. Publish only the exact /ea-console prefix over HTTPS, forwarding WebSocket upgrades; do not publish 6091 or 5901. This deployment uses the isolated HTTPS origin `https://api.nevstore.id:8443` with the existing valid certificate; other API/customer routes are not served on this port. The exact-origin checks include the port, so the normal website origin on 443 cannot access the console transport or connection credential. Access is a one-time bearer capability delivered only to the owner's verified private bot chat; possession of a copied link would confer access, so do not forward it.

## Local CLI

```
/opt/goldshield-console/venv/bin/python tools/web_console.py serve
/opt/goldshield-console/venv/bin/python tools/web_console.py issue-ticket --state-dir /var/lib/goldshield-console --owner-id 1227557858
```

`issue-ticket` prints exactly one JSON object containing `ticket` and `expires_at`. Capture stdout privately in a trusted local helper; never put the ticket in a public URL/query, logs, shell history, or chat. The default allowed owner is 1227557858; `GOLDSHIELD_CONSOLE_OWNER_ID` can explicitly configure the same allowed identity for both CLI and server. Do not run two servers against the same state directory (one live WebSocket per session is process-local).

Tickets and sessions are independent 256-bit random values, stored only as SHA-256 digests in SQLite `auth.sqlite`. Ticket TTL is 900 seconds, session absolute TTL 1800 seconds; expiry at equality is invalid. An atomic BEGIN IMMEDIATE transaction consumes a ticket exactly once. Issuing a ticket revokes all previous tickets and sessions for the configured owner. State directory mode is 0700 and database mode 0600. Use the dedicated service identity for both issuer and server; no bot token belongs in this process.

`serve` reads GOLDSHIELD_CONSOLE_ORIGIN (required exact HTTPS origin), PORT (6091), STATE (/var/lib/goldshield-console), NOVNC (/opt/goldshield-console/noVNC), STATIC (/home/ubuntu/EA-Nevan/deployment/web-console/static), and VNC_PASSWORD_FILE (required systemd credential path), each prefixed `GOLDSHIELD_CONSOLE_`. Bind is always 127.0.0.1. The unit loads only `vnc-password` through systemd credentials, hides MT5/runtime/private credential paths, permits writes only to state, and has 128/192 MiB memory and 25% CPU limits. Keep the dedicated user out of ubuntu/MT5 groups and verify filesystem ACLs when deploying.

## Verification / scope

Run `/home/ubuntu/goldshield-linux/test-venv/bin/python -m unittest discover -s tests -p test_web_console.py -v`. Fixtures use generated temporary state and fake VNC password, with a real ephemeral loopback TCP echo server; they never connect to the desktop or broker. Installing the unit is not part of a unit test.

## Verifikasi deployment nyata

- Unit `goldshield-console.service` telah dijalankan dengan user khusus, credential VNC systemd, filesystem read-only dan jaringan hanya localhost. Nginx mempublikasikan origin TLS terisolasi pada port 8443; 6091/5901 tetap loopback. Konfigurasi host dibandingkan dengan template yang direview.
- noVNC 1.7.0: 56 berkas core/vendor cocok byte-per-byte dengan rilis resmi; aiohttp 3.14.5 sesuai metadata PyPI resmi. Tidak ada broker password di komponen web ini.
- Browser nyata berhasil tersambung ke desktop melalui HTTPS → WebSocket → VNCAuth. Input keyboard HP dibuktikan sampai aplikasi xterm terisolasi memakai teks non-rahasia; aplikasi/probe kemudian dihapus. Tidak ada input akun/order broker dalam pengujian.
- Ukuran viewport 360×800, 390×844, 844×390, 768×1024 dan 1280×800 tidak memiliki overflow halaman atau teks kontrol terpotong. Reload memakai cookie berhasil; logout mencabut sesi dan menghasilkan 401.
- Pengujian live dari origin biasa port 443 ditolak 403; tanpa cookie endpoint koneksi/WebSocket ditolak 401. Shell HTTPS dapat dijangkau dari browser terpisah. API utama, Nevstore dan Boost tetap HTTP 200.
- **Jangan gunakan GET untuk mengambil credential koneksi:** browser tidak selalu menambahkan Origin pada GET same-origin. Kontrak frontend/backend memakai POST dan diuji bersama.
- **Rate limit hanya API/WebSocket, bukan modul statis noVNC.** Membatasi seluruh fan-out modul membuat reload gagal 429. Map Nginx memberi key kosong untuk aset statis; uji browser live membuktikan reconnect setelah perbaikan.
- Suite gabungan saat deployment: 50 tes Python (3 installer Windows dilewati) dan 8 tes UI JavaScript, tanpa kegagalan. Review independen source/security lulus.
- EA tetap pada mode SETUP, unit trading aktif OFF dan sentinel aktivasi tidak dibuat. Login broker oleh pemilik serta impor state sesi PC tetap tahap terpisah.

## Pemulihan koneksi HP yang tersendat

Shell dan pertukaran credential tetap pada origin terisolasi `https://api.nevstore.id:8443`. Transport desktop menggunakan `wss://api.nevstore.id/ea-console/ws` pada TLS standar 443. Pasang `nginx-websocket443.conf` di dalam server HTTPS API: hanya endpoint WebSocket itu yang diproxy; path console lain pada 443 mengembalikan 404. Cookie tetap same-site dan backend tetap memerlukan Origin UI **:8443**; perubahan ini tidak mengizinkan halaman biasa port 443 mengendalikan desktop.

Koneksi frontend dibatasi 20 detik untuk fetch, pemuatan modul dan handshake. Jika belum berhasil, request dibatalkan, koneksi lama dihentikan dan tombol Sambungkan ulang dibuka tanpa mencabut sesi. Callback terlambat dari attempt lama tidak boleh mengubah koneksi baru. Indikator membedakan Memuat layar dari Menyambungkan, dan status tersambung menjelaskan letak File → Login to Trade Account. Penyebab khusus di perangkat/jaringan pengguna tidak disimpulkan dari screenshot saja.

Saat debugging sesi pengguna yang masih valid, jangan membuat tiket baru sekadar untuk mengetes: itu akan mencabut sesi pengguna. Uji transport tanpa credential asli, gunakan fixtures terisolasi, dan minta refresh halaman yang sudah terbuka, bukan membuka ulang fragment sekali pakai. HTTP 200 pada shell bukan bukti WebSocket tersambung.

## Mengirim ulang akses privat

Sebagai root, jalankan `python3 /home/ubuntu/EA-Nevan/tools/send_console_link.py`. Helper memeriksa tujuan chat pribadi pemilik, membuat capability baru, mengirim tombol terlindungi dan memverifikasi readback pesan/tombol. Stdout hanya receipt ID/waktu kedaluwarsa, tanpa link atau credential. Capability baru mencabut seluruh link/sesi pemilik sebelumnya. Jangan menjalankan CLI issue-ticket dengan stdout terbuka di chat, menyalin link ke grup, atau menguji ulang link milik pengguna. Link harus dibuka dalam 15 menit; sesi berlaku 30 menit setelah pertukaran berhasil. Jangan meminta password broker melalui bot atau Telegram.
