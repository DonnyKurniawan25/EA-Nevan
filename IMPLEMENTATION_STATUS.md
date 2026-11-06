# Status implementasi — 6 November 2026 (WITA)

**Pembaruan build 1.201:** pengaman modal US$10 dan template Standard Cent/USC tersedia. Entry real OFF. Model lokal baru tahap riset dan belum disetujui; akun Cent target masih menunggu verifikasi login. Lihat [laporan modal kecil](reports/SMALL_CAPITAL_RESULTS.md).


Pekerjaan tetap bertahap; perbaikan core dan pengujian DEMO dilakukan atas permintaan pengguna. Source tersedia dan kompilasi lulus tidak berarti acceptance keselamatan atau profitabilitas telah lulus.

| Tahap | Status | Bukti / pekerjaan tersisa |
|---|---|---|
| Review API resmi | Dilakukan | `docs/TECHNICAL_REVIEW.md` |
| Struktur, tipe, state machine | Diimplementasikan | EA + 14 header, build 1.101 |
| Phase 1 core standalone | Core, unit, tes historis tersedia; safety lengkap belum lulus | 0 error/warning, 1.036 checks MQL; default SHADOW |
| Phase 2 risk & recovery lengkap | Sebagian pengaman ditambahkan | Realized daily/weekly loss, net loss streak, cap entry dan remaining headroom tersedia; floating/cashflow/fault injection belum selesai |
| Phase 3 MTF/regime/router | Filter H1/pullback eksperimen diuji, tidak dipilih | Hasil belum konsisten; router/regime lengkap belum tersedia |
| Phase 4 research/ONNX | Belum dimulai | Tidak ada dataset broker, model, kalibrasi, atau parity result |
| Phase 5 API/LLM | Belum dimulai | `ApiEnabled=true` ditolak; tidak ada HTTP |
| Phase 6 bounded grid/exits | Belum dimulai | `GridEnabled=true` ditolak; belum ada preset riset grid yang dapat dijalankan |
| Phase 7 dashboard | Opsional, belum dimulai | Website tidak diperlukan untuk core |
| Phase 8 hardening | Sebagian dokumentasi awal | Belum release-approved |

## Acceptance Phase 1

- [x] Source EA dan dependencies tersedia, bukan pseudocode.
- [x] Default SHADOW, kedua toggle entry OFF, real diblokir.
- [x] Memakai indikator MQL5 melalui handle dan candle tertutup.
- [x] SL/TP server-side, magic/comment ownership, executor tunggal ditulis dalam source.
- [x] Petunjuk compile/install, preset, unit harness dan smoke plan tersedia.
- [x] Kontrak source/paket dan matematika portabel benar-benar dijalankan; hasil mesin di `reports/verification.json`.
- [x] `.mq5/.mqh` dan script unit dikompilasi MetaEditor build 6302, 0 error dan 0 warning; `reports/mt5_compile.json`.
- [x] MT5 Exness, source, header, preset dan binary robot dipasang di PC pengguna.
- [x] Script tes MQL build terbaru: 1.036 checks, 0 failures; receipt dan hash pada reports/mt5_runtime.json.
- [x] Startup SHADOW pada akun demo hedging, XAUUSDm M15: RECOVERY → READY, posisi/order akun 0; pintasan desktop tersedia.
- [x] Smoke Strategy Tester SHADOW: 280 bars, 16.772 ticks, 280 HOLD_SPREAD_LIMIT, 0 request order. Ini tes fungsi, bukan G3/performa strategi lengkap.
- [x] Candle live pertama diproses pada 14:30 WITA: HOLD_SPREAD_LIMIT, satu evaluasi untuk candle tersebut, tanpa request order.
- [ ] Seluruh skenario fail/restart/duplicate/exit keselamatan lulus; startup READY saja bukan acceptance keseluruhan.
- [ ] Broker fill/reject/partial fill/disconnect/restart diuji pada demo.

## Gates spesifikasi

| Gate | Status aktual |
|---|---|
| G0 compile/lint MQL5 | LULUS — EA dan script unit, MetaEditor 6302, 0 error dan 0 warning |
| G1 unit | PARSIAL — 40.046 assertions native dan 1.036 checks MQL lulus; integrasi ekstrem belum lengkap |
| G2 safety | BELUM DIVERIFIKASI — kontrak source diuji, bukan fault injection terminal/broker |
| G3 backtest rules | Fungsi/reconciliation/risk checks enam perbandingan dan satu regresi lulus; performa belum konsisten, tidak promosi |
| G4 ONNX parity | BELUM DIIMPLEMENTASIKAN |
| G5 ML research | BELUM DIIMPLEMENTASIKAN |
| G6 shadow live | DIMULAI — akun demo tersambung, XAUUSDm M15 READY; belum evaluasi jangka panjang |
| G7 forward demo | Satu transaksi build lama selesai rugi; entry diparkir OFF, build baru belum forward-approved |
| G8 broker review | BELUM DILAKUKAN |
| G9 real approval | DI LUAR BUILD INI; eksekusi real tidak tersedia |

Satu order entry robot DEMO pernah terkonfirmasi pada build lama, kemudian ditutup oleh SL. Tidak ada eksekusi uang real. Akun/password dibuat dan dimasukkan sendiri oleh pengguna. Build baru dipasang dalam mode pemantauan.
