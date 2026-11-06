"""Compile installed sources with the real MetaEditor and retain the actual logs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def decode_log(path):
    content = path.read_bytes()
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16")
    if b"\x00" in content[:100]:
        return content.decode("utf-16-le")
    return content.decode("utf-8-sig", errors="replace")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--editor", required=True, type=Path)
    parser.add_argument("--mql5-root", required=True, type=Path)
    args = parser.parse_args()
    editor, mql5 = args.editor.resolve(), args.mql5_root.resolve()
    if not editor.is_file() or not (mql5 / "Include/Trade/Trade.mqh").is_file():
        parser.error("MetaEditor or the MT5 Standard Library was not found")
    # Refuse a successful compile of an older installed copy: the binary must
    # correspond to the workspace change being reviewed and tested.
    expected = [(ROOT / "mt5/Experts/GoldShield_AI_V2.mq5", mql5 / "Experts/GoldShield_AI_V2.mq5"),
                (ROOT / "mt5/Tests/GoldShield_SafetyMath_Tests.mq5", mql5 / "Scripts/GoldShield_SafetyMath_Tests.mq5")]
    expected += [(p, mql5 / "Include/GoldShield" / p.name)
                 for p in (ROOT / "mt5/Include/GoldShield").glob("*.mqh")]
    if any(not installed.is_file() or source.read_bytes() != installed.read_bytes()
           for source, installed in expected):
        parser.error("Installed sources differ from workspace; synchronize the source and headers before compiling")
    log_root = ROOT / "reports/compile"
    log_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result = {"editor": str(editor), "mql5_root": str(mql5), "compiled_at_utc": stamp, "targets": []}
    result["header_sha256"] = {
        f"mt5/Include/GoldShield/{path.name}": hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((mql5 / "Include/GoldShield").glob("*.mqh"))
    }
    for relative in ("Experts/GoldShield_AI_V2.mq5", "Scripts/GoldShield_SafetyMath_Tests.mq5"):
        source = mql5 / relative
        if not source.is_file():
            parser.error(f"Install source first: {source}")
        log_file = log_root / f"{source.stem}_{stamp}.log"
        # MetaEditor uses its own switch parser: quotes belong after the colon.
        # This is a direct CreateProcess command line, without any shell interpretation.
        command = f'"{editor}" /compile:"{source}" /inc:"{mql5}" /log:"{log_file}"'
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        started = time.time()
        process = subprocess.run(command, timeout=180, startupinfo=startup, capture_output=True)
        # Existing MetaEditor instances can finish the request shortly after the CLI child exits.
        deadline = time.monotonic() + 30
        text = ""
        while time.monotonic() < deadline:
            if log_file.is_file():
                text = decode_log(log_file)
                if re.search(r"\b\d+ errors?, \d+ warnings?", text):
                    break
            time.sleep(0.5)
        summary = re.search(r"\b(\d+) errors?, (\d+) warnings?", text)
        binary = source.with_suffix(".ex5")
        passed = bool(summary and int(summary[1]) == 0 and binary.is_file()
                      and binary.stat().st_size > 0 and binary.stat().st_mtime >= started - 3)
        target = {"source": str(source), "binary": str(binary), "log": str(log_file),
                  "status": "PASS" if passed else "FAIL", "cli_exit_code": process.returncode,
                  "errors": int(summary[1]) if summary else None,
                  "warnings": int(summary[2]) if summary else None,
                  "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        if passed:
            target["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
            output = ROOT / "dist/mt5" / binary.name
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary, output)
        result["targets"].append(target)
        if text:
            for line in text.splitlines():
                if "Result:" in line or re.search(r"\b(?:warning|error) \d+:", line):
                    print(f"{source.name}: {line.strip()}")
        else:
            print(f"No completed compiler log: {log_file}")
    result["status"] = "PASS" if all(t["status"] == "PASS" for t in result["targets"]) else "FAIL"
    output = ROOT / "reports/mt5_compile.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"MetaEditor result: {result['status']} — {output}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
