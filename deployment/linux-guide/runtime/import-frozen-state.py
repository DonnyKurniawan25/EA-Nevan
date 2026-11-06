"""Import a stopped, flat DEMO20 session into a fresh dedicated Linux terminal.
Run manually after reading the guide. Does not connect to a broker.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Pemakaian: python3 runtime/import-frozen-state.py FOLDER_STATE_PC")
    if os.name != "posix":
        raise SystemExit("Hanya dijalankan manual di Linux tujuan.")
    running = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", r"[t]erminal64\.exe"], capture_output=True)
    if running.returncode != 1:
        raise SystemExit("Tutup seluruh terminal64.exe milik user ini sebelum impor; tidak ada proses yang dihentikan otomatis.")
    if (ROOT / "ACTIVATE_DEMO20").exists() or (ROOT / "state-import-receipt.json").exists():
        raise SystemExit("Sudah pernah diaktifkan/diimpor. Jangan menimpa sesi yang sudah berjalan.")
    executable = os.environ.get("GOLDSHIELD_MT5_EXE")
    if not executable or not Path(executable).is_file():
        raise SystemExit("Jalankan source runtime.env dan periksa lokasi MT5 terlebih dahulu.")
    terminal = Path(executable).resolve().parent
    source = Path(sys.argv[1]).resolve()
    manifest = json.loads((source / "state-manifest.json").read_text(encoding="utf-8-sig"))
    preset = dict(line.split("=", 1) for line in (ROOT / "presets/DEMO20_CURRENT.set").read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith(";"))
    magic = int(preset["MagicNumber"])
    prefix = manifest.get("audit_key", "")
    if manifest.get("magic") != magic or not re.fullmatch(r"GS2\.[A-F0-9]{16}", prefix) or manifest.get("mode") != "DEMO20_FROZEN_PC_STATE":
        raise SystemExit("Identitas state tidak sesuai sesi DEMO20 ini.")
    used = manifest.get("entry_submissions_last_recorded")
    if manifest.get("local_demo_opt_in_disabled") is not True or manifest.get("open_positions_last_recorded") != 0 or type(used) is not int or not 0 <= used <= 20:
        raise SystemExit("Snapshot tidak mengonfirmasi sesi flat, penghitung valid, dan opt-in PC OFF.")
    required = ["bases/gvariables.dat", f"MQL5/Files/GoldShield/{prefix}.lock",
                f"MQL5/Files/GoldShield/{prefix}.csv", f"MQL5/Files/GoldShield/demo20_{magic}.csv"]
    for relative in required:
        file = source / relative
        if not file.is_file() or file.stat().st_size <= 0 or digest(file) != manifest["files"].get(relative):
            raise SystemExit(f"Berkas state hilang/berubah: {relative}")
    old_marker = terminal / "MQL5/Files/GoldShield" / f"{prefix}.lock"
    if old_marker.exists():
        raise SystemExit("Terminal tujuan sudah memiliki state sesi ini. Perlu pemeriksaan; tidak ditimpa.")
    bundle = json.loads((ROOT / "bundle-manifest.json").read_text(encoding="utf-8"))
    copies = [(ROOT / "Experts/GoldShield_DEMO20.ex5", terminal / "MQL5/Experts/GoldShield_DEMO20.ex5")]
    for name in ("DEMO20_CURRENT.set", "DEMO20_SERVER_STAGE.set"):
        copies.append((ROOT / "presets" / name, terminal / "MQL5/Presets/GoldShield" / name))
    for src, dest in copies:
        if digest(src) != bundle["files"][src.relative_to(ROOT).as_posix()]:
            raise SystemExit(f"Berkas paket berubah: {src.name}")
        if dest.exists() and digest(dest) != digest(src):
            raise SystemExit(f"Berkas tujuan berbeda; tidak ditimpa: {dest}")
    bases = next((p for p in terminal.iterdir() if p.is_dir() and p.name.lower() == "bases"), terminal / "bases")
    bases.mkdir(exist_ok=True)
    global_file = bases / "gvariables.dat"
    if global_file.exists():
        backup = ROOT / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(global_file, backup / "gvariables-before-import.dat")
    state_copies = [(source / relative, terminal / relative) for relative in required[1:]]
    state_copies.append((source / required[0], global_file))
    for src, dest in copies + state_copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if digest(src) != digest(dest):
            raise SystemExit(f"Verifikasi hasil salin gagal: {dest}")
    receipt = {"imported_at_utc": datetime.now(timezone.utc).isoformat(), "magic": magic,
               "audit_key": prefix, "source_state_manifest_sha256": digest(source / "state-manifest.json"),
               "entry_submissions_last_recorded": manifest["entry_submissions_last_recorded"],
               "global_variables_sha256_at_import": digest(global_file), "broker_orders_sent": 0,
               "status": "IMPORTED_ONLY_REQUIRES_MANUAL_STAGE_VERIFICATION"}
    (ROOT / "state-import-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("Impor tersalin dan sidik berkas cocok. Belum ada robot/order dijalankan. Lanjutkan tahap STAGE di panduan.")


if __name__ == "__main__":
    main()
