# Jalankan sendiri di PC HANYA ketika benar-benar akan berpindah ke server.
# Syarat: tab Trade kosong, Algo Trading OFF, lalu MT5 sudah ditutup.
# Menyalin state dan menonaktifkan opt-in preset DEMO20 lokal.
# Tidak mengakses server, mengubah algoritma, atau preset real Cent.
$ErrorActionPreference = 'Stop'
if (Get-Process -Name terminal64 -ErrorAction SilentlyContinue) {
    throw 'Tutup MT5 terlebih dahulu setelah memastikan tidak ada posisi/pending order.'
}
$goldGuideRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$goldSettingsPath = Join-Path $goldGuideRoot 'migration-settings.local.json'
if (-not (Test-Path -LiteralPath $goldSettingsPath)) {
    throw 'Salin migration-settings.example.json menjadi migration-settings.local.json dan isi sesuai terminal Anda dahulu.'
}
$goldSettings = Get-Content -LiteralPath $goldSettingsPath -Raw | ConvertFrom-Json
$goldData = [string]$goldSettings.mt5_data_folder
$goldMagic = [long]$goldSettings.magic
$goldKey = [string]$goldSettings.audit_key
if (-not (Test-Path -LiteralPath $goldData -PathType Container) -or $goldMagic -le 0 -or $goldKey -notmatch '^GS2\.[A-F0-9]{16}$') {
    throw 'Folder data, magic atau audit_key belum valid. Ambil dari terminal dan panel sesi yang benar.'
}
$goldStatusPath = Join-Path $goldData "MQL5\Files\GoldShield\demo20_$goldMagic.csv"
$goldStatus = Import-Csv -LiteralPath $goldStatusPath | Select-Object -Last 1
if ($goldStatus.account_mode -ne 'DEMO' -or $goldStatus.symbol -ne 'XAUUSDm' -or [int]$goldStatus.open_positions -ne 0 -or [int]$goldStatus.entry_submissions -gt 20) {
    throw 'Status terakhir bukan sesi demo flat yang sesuai. Periksa dahulu; tidak ada berkas disalin.'
}
$goldDesktop = [Environment]::GetFolderPath('Desktop')
$goldOut = Join-Path $goldDesktop ('DEMO20-STATE-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $goldOut | Out-Null
$goldFiles = @('bases/gvariables.dat', "MQL5/Files/GoldShield/$goldKey.lock", "MQL5/Files/GoldShield/$goldKey.csv", "MQL5/Files/GoldShield/demo20_$goldMagic.csv")
$goldHashes = [ordered]@{}
foreach ($goldRelative in $goldFiles) {
    $goldSource = Join-Path $goldData $goldRelative
    if (-not (Test-Path -LiteralPath $goldSource -PathType Leaf)) { throw "Berkas state tidak ditemukan: $goldRelative" }
    $goldTarget = Join-Path $goldOut $goldRelative
    New-Item -ItemType Directory -Path (Split-Path $goldTarget) -Force | Out-Null
    Copy-Item -LiteralPath $goldSource -Destination $goldTarget
    $goldSourceHash = (Get-FileHash -LiteralPath $goldSource -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $goldTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $goldSourceHash) { throw 'Verifikasi salinan gagal.' }
    $goldHashes[$goldRelative] = $goldSourceHash
}
$goldLocalPreset = Join-Path $goldData 'MQL5\Presets\GoldShield\DEMO20_CURRENT.set'
$goldText = Get-Content -LiteralPath $goldLocalPreset -Raw
if ($goldText -notmatch ("(?m)^MagicNumber=" + $goldMagic + '\s*$') -or $goldText -notmatch '(?m)^AllowRealTrading=false\s*$') {
    throw 'Preset lokal tidak sesuai. Sesi server jangan diaktifkan.'
}
Copy-Item -LiteralPath $goldLocalPreset -Destination (Join-Path $goldOut 'LocalPresetBeforeFreeze.set')
$goldText = $goldText -replace '(?m)^EnableAutoTrading=true\r?$', 'EnableAutoTrading=false'
$goldText = $goldText -replace '(?m)^DemoTradingOptIn=true\r?$', 'DemoTradingOptIn=false'
$goldText | Set-Content -LiteralPath $goldLocalPreset -Encoding ASCII
$goldCheck = Get-Content -LiteralPath $goldLocalPreset -Raw
if ($goldCheck -notmatch '(?m)^EnableAutoTrading=false\s*$' -or $goldCheck -notmatch '(?m)^DemoTradingOptIn=false\s*$') {
    throw 'Opt-in lokal belum terverifikasi OFF. Jangan mengaktifkan server.'
}
$goldManifest = [ordered]@{
    mode = 'DEMO20_FROZEN_PC_STATE'
    created_at_wita = (Get-Date).ToString('o')
    magic = $goldMagic
    audit_key = $goldKey
    entry_submissions_last_recorded = [int]$goldStatus.entry_submissions
    open_positions_last_recorded = [int]$goldStatus.open_positions
    local_demo_opt_in_disabled = $true
    note = 'Global variables are authoritative. Verify exact counter/reference on STAGE; do not reset or lower values.'
    files = $goldHashes
}
$goldManifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $goldOut 'state-manifest.json') -Encoding UTF8
Write-Output "State tersimpan: $goldOut"
Write-Output 'Opt-in preset DEMO20 lokal sudah OFF. Jangan aktifkan lagi selama server menjalankan sesi ini.'
