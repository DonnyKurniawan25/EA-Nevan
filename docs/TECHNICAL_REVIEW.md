# Review spesifikasi terhadap API resmi

Review dilakukan sebelum dan selama implementasi Phase 1. Bagian 23–41 dan prompt Phase 1 pada bagian 39 menjadi prioritas atas baseline yang meminta RULES/order demo lebih awal.

| Pokok | Penyesuaian source |
|---|---|
| SHADOW vs `SignalMode=RULES` baseline | Eksekusi dan metode sinyal dipisah secara konseptual. Build ini hanya baseline RULES; `ExecutionMode=SHADOW` default |
| iMA/iRSI/iATR | Membuat handle, memeriksa `BarsCalculated`, mengambil nilai lewat `CopyBuffer` shift 1, melepas handle saat deinit |
| OrderCheck vs OrderSend retcodes | Contoh resmi `OrderCheck` menghasilkan success retcode **0**, sedangkan DONE pengiriman umumnya 10009. Source menerima check code 0/DONE hanya bersama return boolean valid dan margin checks; tidak menyamakan check dengan fill |
| `CTrade.PositionOpen` true | Tetap memeriksa/log `ResultRetcode`, order/deal/filled values; posisi broker diperlukan untuk konfirmasi |
| Event transaksi | Callback dapat berulang dan urutannya tidak dijamin. Tidak menghitung callback sebagai jumlah posisi/fill |
| Hedging close | Menggunakan `PositionClose(ticket)`, verifikasi symbol/magic/comment; tidak memakai close berdasarkan simbol |
| Broker units | Harga di-grid ke tick size; lot ke volume step ke bawah. `OrderCalcProfit`/`OrderCalcMargin` menentukan estimasi mata uang akun |
| Filling | Mengikuti FOK/IOC flags; RETURN ditolak untuk Market Execution bila tak didukung |
| Stops | Memeriksa broker SL/TP flags, stops/freeze distance secara konservatif; SL/TP dikirim sejak request awal |
| Include resolution | Seluruh header memakai `<GoldShield/...>` di lokasi standar `MQL5/Include`; dependency proyek tidak bergantung pada current-directory quotes |
| Timezones | Waktu candle/tick/sesi memakai server broker. `TimeGMT` dicatat terpisah sebagai UTC PC pada live; tester tidak mengarang UTC dari server time |
| WebRequest | Tidak digunakan di Phase 1. API/Telegram masa depan perlu menjaga event loop lokal; `OnTimer` bukan background thread |
| GlobalVariable persistence | Variabel terminal memiliki masa retensi; sentinel file mencegah reset otomatis ketika state hilang. Belum menjadi storage/recovery production penuh |

Referensi primer:

- [OrderCheck, termasuk contoh retcode](https://www.mql5.com/en/docs/trading/ordercheck)
- [OrderSend dan batas makna return true](https://www.mql5.com/en/docs/trading/ordersend)
- [CTrade PositionOpen](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/ctrade/ctradepositionopen)
- [OnTradeTransaction](https://www.mql5.com/en/docs/event_handlers/ontradetransaction)
- [Symbol properties, filling, stops dan volume](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)
- [Include directive](https://www.mql5.com/en/docs/basis/preprosessor/include)
- [Global variables](https://www.mql5.com/en/docs/globals)
- [WebRequest](https://www.mql5.com/en/docs/network/webrequest)
- [Kompilasi MetaEditor](https://www.metatrader5.com/en/metaeditor/help/development/compile)

Review dokumen/API tidak menggantikan kompilasi terhadap versi MetaEditor yang digunakan atau pengujian spesifikasi broker sebenarnya.
