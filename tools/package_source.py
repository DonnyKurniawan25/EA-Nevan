"""Create a source-only ZIP and reproducible file checksums; never includes native builds/secrets."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"build", "dist", "__pycache__", ".pytest_cache", ".git"}
EXTENSIONS = {".ex5", ".exe", ".obj", ".pyc", ".log", ".token", ".secret"}


def main():
    files = [p for p in ROOT.rglob("*") if p.is_file()
             and not (set(p.relative_to(ROOT).parts) & EXCLUDED)
             and p.suffix.lower() not in EXTENSIONS
             and not p.name.startswith(".env") and p.name != "SHA256SUMS.txt"]
    files.sort(key=lambda p: p.relative_to(ROOT).as_posix())
    manifest = ROOT / "SHA256SUMS.txt"
    manifest.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n" for p in files), encoding="utf-8")
    files.append(manifest)
    output = ROOT / "dist/goldshield-ai-v2-phase1-source.zip"
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo("goldshield-ai-v2/" + path.relative_to(ROOT).as_posix(), date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity verification failed")
    print(f"Source package: {output} ({len(files)} files)")
    print(f"SHA256: {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
