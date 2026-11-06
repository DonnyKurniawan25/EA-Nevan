#!/usr/bin/env bash
# Template peluncur; belum diuji pada server pengguna.
set -euo pipefail
GOLD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$GOLD_ROOT/runtime.env"
if [[ -f "$GOLD_ROOT/runtime.local.env" ]]; then source "$GOLD_ROOT/runtime.local.env"; fi
GOLD_MODE="${1:-run}"
GOLD_DIR="$(dirname -- "$GOLDSHIELD_MT5_EXE")"
case "$GOLD_MODE" in
  setup) GOLD_CONFIG="$GOLD_ROOT/config/SETUP.ini" ;;
  stage|run)
    [[ -f "$GOLD_ROOT/state-import-receipt.json" ]] || { echo 'Impor state sesi PC terlebih dahulu.' >&2; exit 1; }
    [[ -s "$GOLD_DIR/bases/gvariables.dat" || -s "$GOLD_DIR/Bases/gvariables.dat" ]] || { echo 'State terminal hilang; tidak memulai robot.' >&2; exit 1; }
    GOLD_SESSION_KEY="$(python3 -c 'import json,re,sys; k=json.load(open(sys.argv[1],encoding="utf-8"))["audit_key"]; assert re.fullmatch(r"GS2\.[A-F0-9]{16}",k); print(k)' "$GOLD_ROOT/state-import-receipt.json")"
    [[ -s "$GOLD_DIR/MQL5/Files/GoldShield/$GOLD_SESSION_KEY.lock" ]] || { echo 'Penanda sesi asli hilang.' >&2; exit 1; }
    if [[ "$GOLD_MODE" == run ]]; then
      [[ -f "$GOLD_ROOT/ACTIVATE_DEMO20" ]] || { echo 'Verifikasi tahap STAGE dan aktifkan secara manual sesuai panduan.' >&2; exit 1; }
      GOLD_CONFIG="$GOLD_ROOT/config/SERVER_DEMO20.ini"
    else
      GOLD_CONFIG="$GOLD_ROOT/config/STAGE.ini"
    fi ;;
  *) echo 'Gunakan: start-mt5.sh setup|stage|run' >&2; exit 2 ;;
esac
[[ -f "$GOLDSHIELD_MT5_EXE" ]] || { echo 'Lokasi terminal64.exe tidak ditemukan; periksa runtime.env.' >&2; exit 1; }
for GOLD_CMD in wine winepath xdpyinfo flock pgrep python3; do
  command -v "$GOLD_CMD" >/dev/null || { echo "Program belum tersedia: $GOLD_CMD" >&2; exit 1; }
done
exec 9>"$GOLD_ROOT/mt5-launch.lock"
flock -n 9 || { echo 'Peluncur MT5 untuk direktori ini masih berjalan.' >&2; exit 1; }
if pgrep -u "$(id -u)" -f '[t]erminal64\.exe' >/dev/null; then
  echo 'Masih ada terminal64.exe milik user ini. Tutup melalui File > Exit sebelum memulai yang baru.' >&2
  exit 1
fi
GOLD_DISPLAY_READY=0
for GOLD_ATTEMPT in {1..30}; do
  if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then GOLD_DISPLAY_READY=1; break; fi
  sleep 1
done
[[ "$GOLD_DISPLAY_READY" == 1 ]] || { echo 'Desktop belum siap; periksa goldshield-desktop.service.' >&2; exit 1; }
GOLD_WIN_CONFIG="$(winepath -w "$GOLD_CONFIG")"
cd -- "$GOLD_DIR"
exec wine "$GOLDSHIELD_MT5_EXE" /portable "/config:$GOLD_WIN_CONFIG"
