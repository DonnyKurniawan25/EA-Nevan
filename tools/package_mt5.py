"""Package verified EX5 files with source, headers, presets, and setup notes. No credentials."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    compile_report = json.loads((ROOT / "reports/mt5_compile.json").read_text(encoding="utf-8"))
    if compile_report.get("status") != "PASS":
        raise RuntimeError("Real MetaEditor compilation must pass before binary packaging")
    entries = []
    for target in compile_report["targets"]:
        if target.get("errors") != 0 or target.get("warnings") != 0:
            raise RuntimeError("Expected zero errors and warnings")
        binary = Path(target["binary"])
        if hashlib.sha256(binary.read_bytes()).hexdigest() != target["binary_sha256"]:
            raise RuntimeError("Compiled binary changed after verification")
        group = "Experts" if binary.stem == "GoldShield_AI_V2" else "Scripts"
        entries.append((binary, f"MQL5/{group}/{binary.name}"))
    for relative, digest in compile_report["header_sha256"].items():
        path = ROOT / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Header changed after compilation")
        entries.append((path, "MQL5/" + path.relative_to(ROOT / "mt5").as_posix()))
    for path in sorted((ROOT / "mt5/Presets").glob("*.set")):
        entries.append((path, "MQL5/Presets/GoldShield/" + path.name))
    entries += [(ROOT / "docs/PC_SETUP.md", "MULAI_DI_SINI.md"),
                (ROOT / "docs/MULAI_DI_SINI.txt", "MULAI_DI_SINI.txt"),
                (ROOT / "deployment/windows-vps/GoldShield_SHADOW.ini", "GoldShield_SHADOW.ini"),
                (ROOT / "docs/LIMITATIONS.md", "LIMITATIONS.md"),
                (ROOT / "reports/RUNTIME_TEST_RESULTS.md", "RUNTIME_TEST_RESULTS.md"),
                (ROOT / "reports/DEMO_TEST_RESULTS.md", "DEMO_TEST_RESULTS.md"),
                (ROOT / "reports/IMPROVEMENT_RESULTS.md", "IMPROVEMENT_RESULTS.md"),
                (ROOT / "reports/SMALL_CAPITAL_RESULTS.md", "SMALL_CAPITAL_RESULTS.md"),
                (ROOT / "reports/mt5_compile.json", "mt5_compile.json")]
    output = ROOT / "dist/GOLDSHIELD_MT5_SHADOW.zip"
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, relative in entries:
            archive.write(path, "GOLDSHIELD_MT5_SHADOW/" + relative)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
    print(f"Verified MT5 package: {output}; {len(entries)} files")


if __name__ == "__main__":
    main()
