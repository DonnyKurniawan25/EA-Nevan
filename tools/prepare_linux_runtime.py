"""Verify and copy Linux templates into a fresh operator directory.
No server access, package installation, credentials, services or trade operations.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "deployment/linux-guide"
FORBIDDEN = {"ACTIVATE_DEMO20", "state-import-receipt.json", "migration-settings.local.json",
             "runtime.local.env", "gvariables.dat", "accounts.dat"}


def prepare(destination):
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Folder tujuan sudah ada. Gunakan folder baru; runtime/state lama tidak ditimpa.")
    manifest_path = BUNDLE / "bundle-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest["files"]
    if not files:
        raise ValueError("Manifest paket kosong.")
    verified = []
    for name, expected in files.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or relative.name in FORBIDDEN:
            raise ValueError("Manifest berisi jalur/berkas yang tidak diizinkan.")
        source = BUNDLE.joinpath(*relative.parts)
        if source.is_symlink() or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Sidik berkas tidak cocok: {name}")
        verified.append((source, relative))
    destination.mkdir(parents=True, exist_ok=False)
    for source, relative in verified:
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(manifest_path, destination / "bundle-manifest.json")
    for name in ("runtime/start-mt5.sh", "runtime/vnc-xstartup"):
        target = destination / name
        target.chmod(target.stat().st_mode | 0o100)
    return len(verified) + 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    try:
        count = prepare(args.destination)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Persiapan dihentikan: {exc}\n")
    print(f"{count} berkas terverifikasi disalin ke {args.destination.expanduser().absolute()}.")
    print("Belum memasang/menjalankan MT5 atau trading. Lanjutkan PANDUAN_SERVER_LINUX.md.")
