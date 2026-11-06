# Risiko, asumsi dan batas pengaman

Build ini untuk pengembangan core, belum forward-demo approved. Aturan broker, metadata simbol dan pengujian demo menentukan apakah konfigurasi layak digunakan; nama “AI” tidak memberi jaminan hasil.

- Risiko awal berbasis % equity dan kerugian pada SL dalam mata uang akun, ditambah buffer persentase dan biaya per lot. Estimasi tidak mencakup semua kemungkinan gap/slippage.
- Account exposure membaca seluruh posisi, termasuk manual/magic lain, tetapi executor hanya memodifikasi ticket milik EA ini. Semua pending order akun memblokir entry karena risiko reservasinya belum dimodelkan.
- Posisi akun lain tanpa SL, quote yang tak tersedia, atau stop yang telah dilampaui memblokir entry. Jangan menghapus posisi manual agar bot bisa berjalan; review exposure dan kebijakan akun.
- Symbol stop/freeze, SL/TP availability, filling, broker trade mode dan sesi diperiksa. Constraint dapat berubah setelah preflight; retcode dan posisi aktual tetap perlu diperiksa.
- Equity reference persisten adalah equity ketika state dibuat, tidak otomatis mengikuti deposit/withdrawal atau high-water mark. Hard latch memblokir entry dan mencoba close EA dalam mode demo opt-in. Tidak ada auto resume.
- Build 1.101 membaca realized trading P/L harian/mingguan akun dari history broker, termasuk biaya deal dan negative ancillary charges. Deposit/withdrawal/credit dikecualikan. Loss streak memakai net profit+commission+swap+fee posisi EA yang benar-benar tertutup; dua kerugian beruntun memblokir entry sampai hari broker berikutnya. Cap entry menghitung posisi unik. Sisa budget harian/mingguan/equity shield membatasi ukuran entry sebelum request; profit tidak memperbesar budget. History tidak tersedia menghasilkan HOLD. Daily/weekly floating drawdown latch, cashflow-adjusted reference dan fault injection lengkap masih belum tersedia.
- Request awal selalu berisi broker SL/TP. Saat terminal mati, pengaman lokal, panel, CSV, dan virtual emergency close tidak berjalan. Stop broker dapat mengalami gap/slippage atau tidak tersedia saat market tutup.
- Kegagalan close dibatasi dan dicatat; setelah tiga percobaan, operator harus memeriksa sisa posisi. Menyembunyikan sisa posisi sebagai “closed” tidak diperbolehkan.
- SHADOW/DRY_RUN sama sekali tidak melakukan close/modification; bila ada posisi lama, stop broker masih aktif sepanjang tidak diubah dari luar.

Semua saldo, komisi, profit/loss dan margin berunit currency akun. USC/cent dan USD/Standard tidak boleh dipertukarkan hanya lewat angka saldo. Lot antar simbol/broker tidak setara; cap lot mentah hanyalah pembatas tambahan di samping perhitungan uang/margin.
