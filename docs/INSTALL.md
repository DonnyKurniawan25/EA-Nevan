# Instalasi dan kompilasi MT5

Build Phase 1 telah dikompilasi pada MetaEditor 6302 dengan 0 error dan 0 warning serta dipasang di MT5 Exness PC ini. Petunjuk berikut tetap dapat dipakai untuk instalasi ulang/PC lain. Runtime demo belum disahkan untuk forward trading.

1. Buka MT5 Desktop Windows, pilih akun demo **hedging**. Netting ditolak secara eksplisit.
2. Buka `File → Open Data Folder`, masuk `MQL5`. Catat folder tersebut; jangan menebak folder instalasi.
3. Salin `mt5/Experts/GoldShield_AI_V2.mq5` ke `MQL5/Experts/`.
4. Salin folder `mt5/Include/GoldShield/` lengkap ke `MQL5/Include/GoldShield/`. Standard Library `MQL5/Include/Trade/Trade.mqh` harus tersedia dari MT5.
5. Salin `mt5/Tests/GoldShield_SafetyMath_Tests.mq5` ke `MQL5/Scripts/`. Preset bisa dimuat langsung dari folder proyek.
6. Buka EA di MetaEditor, tekan **F7**. Periksa seluruh Errors/Warnings. `.ex5` hanya muncul bila kompilasi berhasil; jangan mengganti ekstensi `.mq5` menjadi `.ex5`.
7. Compile script tes dengan F7 juga, jalankan di chart demo. Script hanya menguji fungsi matematika; tidak mengirim order.
8. Pada MT5, refresh Navigator, buka chart simbol **persis** yang tersedia pada broker, timeframe sesuai input (default M15).
9. Pasang EA dengan `SHADOW_ONLY.set`, pastikan `EnableAutoTrading=false`, `DemoTradingOptIn=false`, `AllowRealTrading=false`. Bila simbol broker `XAUUSDc`, ubah `TradeSymbol` menjadi `XAUUSDc` secara sengaja. Tidak ada pemilihan suffix otomatis.
10. Ikuti `mt5/Tests/TEST_PLAN.md`. Simpan log kompilasi, Journal, CSV dan laporan tester sebagai bukti gate. Jangan mengaktifkan fase berikutnya hanya karena source tersedia.

## Installer source opsional

Dari folder proyek:

```powershell
.\tools\Install-MT5.ps1 -Mql5Root 'C:\lokasi-data-terminal\MQL5'
```

Ganti path dengan hasil `Open Data Folder`. Installer menyalin source/preset/script tes dan menolak file existing yang berbeda sebelum menyalin apa pun. Cadangkan dan pindahkan versi lama untuk update. Installer source tidak menjalankan MT5, tidak mengaktifkan Algo Trading, tidak login dan tidak membuka order. Pengujian otomatis memakai folder sementara berbentuk struktur MT5; installer juga telah dijalankan terhadap instalasi MT5 Exness nyata pada PC ini.

Kompilasi berulang dengan log asli:

```powershell
python .\tools\compile_mt5.py --editor 'C:\Program Files\MetaTrader 5 EXNESS\MetaEditor64.exe' --mql5-root 'PATH-DATA-TERMINAL\MQL5'
```

Path aktual pemasangan ada pada `docs/PC_SETUP.md`. Perintah ini hanya mengompilasi, tidak menjalankan transaksi.

## Penyimpanan dan HTTP

Audit runtime: `MQL5/Files/GoldShield/GS2.<hash>.csv`; lock/sentinel: `.lock` dengan hash yang sama. Global Variables dapat dilihat lewat F3 pada MT5; key ditampilkan di panel. Pada Strategy Tester lokasi file mengikuti sandbox agent tester.

Tidak perlu whitelist WebRequest atau memasukkan API key/token. API dan Telegram belum ada pada Phase 1; mengaktifkan toggle-nya akan menolak init. Jangan menyimpan credential pada `.set` atau source.
