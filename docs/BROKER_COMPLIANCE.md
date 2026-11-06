# Checklist broker sebelum pengujian forward / real

Tidak ada broker dikunci atau otomatis dianggap mengizinkan strategi. Isi checklist dengan data dari broker/terminal sebenarnya. Build ini belum mendukung real trading.

- [ ] Izin EA dan prosedur notifikasi/persetujuan broker dikonfirmasi.
- [ ] Jenis akun hedging; demo, bukan akun real.
- [ ] Nama simbol/suffix exact, currency akun, contract size, tick size/value.
- [ ] Volume min/max/step/limit, order frequency dan filling policy.
- [ ] Stops/freeze levels, market sessions, maintenance/rollover, swap dan komisi.
- [ ] Leverage, margin calculation, margin call dan stop-out thresholds.
- [ ] Stop behavior saat gap, requote, reject, partial fill dan market closed.
- [ ] Batas spread/slippage/buffer biaya sesuai simbol dan denomination akun.
- [ ] Aturan grid/averaging/news/AI API ditinjau jika fitur tersebut kelak dibuat.
- [ ] Tidak menyamakan 40.000 USC dengan 40.000 USD atau menyetarakan contract exposure antar akun.
- [ ] G0–G8 dibuktikan sebelum mempertimbangkan proses real manual terpisah.

Catat sumber kebijakan, tanggal, akun demo yang digunakan (masked), nama simbol dan hasil pengukuran. Jangan menaruh password atau identitas pribadi di laporan.
