"""Exercise the actual source installer against temporary MT5-shaped directories, without MT5."""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows PowerShell installer")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="goldshield-installer-test-")
        self.base = Path(self.temporary.name).resolve()
        # Verify the cleanup target is confined to the OS temporary directory.
        if not self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("Temporary workspace escaped expected directory")
        self.addCleanup(self.temporary.cleanup)
        self.target = self.base / "MQL5"
        trade = self.target / "Include/Trade/Trade.mqh"
        trade.parent.mkdir(parents=True)
        trade.write_text("// Test fixture: no broker, no MT5 executable\n", encoding="utf-8")

    def install(self, target=None):
        return subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               str(ROOT / "tools/Install-MT5.ps1"), "-Mql5Root", str(target or self.target)],
                              text=True, capture_output=True, timeout=30)

    def test_installs_all_source_and_second_run_is_idempotent(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        ea = self.target / "Experts/GoldShield_AI_V2.mq5"
        self.assertEqual(ea.read_bytes(), (ROOT / "mt5/Experts/GoldShield_AI_V2.mq5").read_bytes())
        for header in (ROOT / "mt5/Include/GoldShield").glob("*.mqh"):
            self.assertEqual(header.read_bytes(), (self.target / "Include/GoldShield" / header.name).read_bytes())
        self.assertTrue((self.target / "Scripts/GoldShield_SafetyMath_Tests.mq5").is_file())
        self.assertEqual(len(list((self.target / "Presets/GoldShield").glob("*.set"))),
                         len(list((ROOT / "mt5/Presets").glob("*.set"))))
        before = {p.relative_to(self.target): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.target.rglob("*") if p.is_file()}
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        after = {p.relative_to(self.target): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_conflict_preflight_preserves_existing_file_and_makes_no_other_copy(self):
        existing = self.target / "Include/GoldShield/Storage.mqh"
        existing.parent.mkdir(parents=True)
        existing.write_text("user-owned existing source\n", encoding="utf-8")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("File berbeda sudah ada", result.stderr)
        self.assertEqual(existing.read_text(), "user-owned existing source\n")
        self.assertFalse((self.target / "Experts/GoldShield_AI_V2.mq5").exists())

    def test_wrong_target_root_is_rejected(self):
        wrong = self.base / "UnrelatedFolder"
        wrong.mkdir()
        result = self.install(wrong)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Pilih folder MQL5", result.stderr)
        self.assertFalse(list(wrong.iterdir()))
