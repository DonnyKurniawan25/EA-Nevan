param([Parameter(Mandatory = $true)][string]$Mql5Root)
$ErrorActionPreference = 'Stop'
function Get-ContentDigest([string]$LiteralPath) {
    $stream = [IO.File]::OpenRead($LiteralPath)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [Convert]::ToBase64String($algorithm.ComputeHash($stream)) }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$targetRoot = (Resolve-Path -LiteralPath $Mql5Root).Path.TrimEnd('\')
if ((Split-Path -Leaf $targetRoot) -ne 'MQL5') { throw 'Pilih folder MQL5 dari File > Open Data Folder di MT5.' }
if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'Include\Trade\Trade.mqh'))) {
    throw 'Standard Library MT5 tidak ditemukan. Periksa folder MQL5 yang dipilih.'
}
$plan = @()
$plan += [pscustomobject]@{ Source = Join-Path $projectRoot 'mt5\Experts\GoldShield_AI_V2.mq5'; Relative = 'Experts\GoldShield_AI_V2.mq5' }
$plan += [pscustomobject]@{ Source = Join-Path $projectRoot 'mt5\Tests\GoldShield_SafetyMath_Tests.mq5'; Relative = 'Scripts\GoldShield_SafetyMath_Tests.mq5' }
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $projectRoot 'mt5\Include\GoldShield') -Filter '*.mqh' -File) {
    $plan += [pscustomobject]@{ Source = $file.FullName; Relative = "Include\GoldShield\$($file.Name)" }
}
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $projectRoot 'mt5\Presets') -Filter '*.set' -File) {
    $plan += [pscustomobject]@{ Source = $file.FullName; Relative = "Presets\GoldShield\$($file.Name)" }
}
# Validate every target and every existing file before making changes.
foreach ($item in $plan) {
    $destination = [IO.Path]::GetFullPath((Join-Path $targetRoot $item.Relative))
    if (-not $destination.StartsWith($targetRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Target keluar dari folder MQL5.' }
    if (Test-Path -LiteralPath $destination) {
        if ((Get-ContentDigest $destination) -ne (Get-ContentDigest $item.Source)) {
            throw "File berbeda sudah ada. Cadangkan atau pindahkan file tersebut sebelum memasang: $destination"
        }
    }
}
foreach ($item in $plan) {
    $destination = Join-Path $targetRoot $item.Relative
    if (-not (Test-Path -LiteralPath $destination)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $item.Source -Destination $destination
    }
}
Write-Output 'Source terpasang. Buka GoldShield_AI_V2.mq5 di MetaEditor dan tekan F7. Terminal tidak dijalankan dan trading tidak diaktifkan.'
