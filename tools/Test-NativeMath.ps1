param([string]$VisualStudioRoot = '')
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    if (-not $VisualStudioRoot) {
        $locator = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
        if (-not (Test-Path -LiteralPath $locator)) { throw 'MSVC tidak ditemukan. Native math test belum dijalankan.' }
        $VisualStudioRoot = & $locator -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    }
    if (-not $VisualStudioRoot) { throw 'Visual Studio C++ tools tidak ditemukan.' }
    & (Join-Path $VisualStudioRoot 'Common7\Tools\Launch-VsDevShell.ps1') -Arch amd64 -HostArch amd64 -SkipAutomaticLocation | Out-Null
}
$buildRoot = Join-Path $projectRoot 'build'
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$source = Join-Path $projectRoot 'tests\native_safety_math.cpp'
$program = Join-Path $buildRoot 'native_safety_math.exe'
$objectFile = Join-Path $buildRoot 'native_safety_math.obj'
& cl.exe /nologo /std:c++17 /EHsc /W4 /WX $source "/Fe:$program" "/Fo:$objectFile"
if ($LASTEXITCODE -ne 0) { throw 'Native safety math compilation failed.' }
& $program
if ($LASTEXITCODE -ne 0) { throw 'Native safety math tests failed.' }
