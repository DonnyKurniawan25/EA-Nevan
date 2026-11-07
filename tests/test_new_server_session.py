"""Fresh-server fixtures only: never reads a real terminal or broker account."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('new_server_session', ROOT / 'tools/new_server_session.py')
assert SPEC is not None and SPEC.origin is not None
session = importlib.util.module_from_spec(SPEC)
if SPEC.loader and Path(SPEC.origin).exists():
    SPEC.loader.exec_module(session)


class NewSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / 'fresh-demo'
        self.terminal = self.root / 'terminal'
        self.terminal.mkdir()
        (self.terminal / 'terminal64.exe').write_bytes(b'fixture terminal')

    def prepare(self):
        return session.prepare(self.directory, self.terminal, magic=123456789)

    def test_prepare_new_isolated_stage_and_active(self):
        self.assertTrue(hasattr(session, 'prepare'), 'prepare behavior missing')
        meta = self.prepare()
        self.assertEqual(meta['status'], 'FRESH_SERVER_DEMO20')
        self.assertEqual(meta['magic'], 123456789)
        stage = Path(meta['presets']['stage']).read_text()
        active = Path(meta['presets']['active']).read_text()
        self.assertIn('EnableAutoTrading=false', stage)
        self.assertIn('DemoTradingOptIn=false', stage)
        self.assertIn('EnableAutoTrading=true', active)
        self.assertIn('AllowLiveTrading=0', (self.directory / 'STAGE.ini').read_text())
        self.assertIn('\nEnabled=0\n', (self.directory / 'STAGE.ini').read_text())
        self.assertIn('Script=GoldShield_ServerPreflight', (self.directory / 'STAGE.ini').read_text())
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        base = session.parse_set(ROOT / 'deployment/linux-guide/presets/DEMO20_CURRENT.set')
        for name in ('stage', 'active'):
            generated = session.parse_set(Path(meta['presets'][name]))
            for key in base.keys() - {'MagicNumber', 'EnableAutoTrading', 'DemoTradingOptIn'}:
                self.assertEqual(base[key], generated[key])
        with self.assertRaises(session.GuardError):
            self.prepare()

    def test_prepare_pins_session_owned_profile_with_existing_casing(self):
        charts = self.terminal / 'MQL5/profiles/charts'
        charts.mkdir(parents=True)
        meta = self.prepare()
        expected = 'GS_Server_fresh-demo_' + meta['nonce'][:8]
        self.assertEqual(meta.get('profile_name'), expected)
        self.assertEqual(meta['profile_dir'], str(charts / expected))
        for name in ('PREFLIGHT', 'STAGE', 'RUN'):
            path = self.directory / (name + '.ini')
            self.assertIn('[Charts]\nProfileLast=' + expected + '\n', path.read_text())
            self.assertEqual(meta['hashes'][str(path)], session.digest(path))
        self.assertFalse((charts / expected).exists())

    def legacy_prepared(self):
        meta = self.prepare()
        meta.pop('profile_name'); meta.pop('profile_dir')
        for name in ('PREFLIGHT', 'STAGE', 'RUN'):
            path = self.directory / (name + '.ini')
            path.write_text(path.read_text().split('\n', 2)[2])
            meta['hashes'][str(path)] = session.digest(path)
        (self.directory / 'session.json').write_text(json.dumps(meta))
        return meta

    def test_upgrade_preserves_identity_presets_and_terminal_state(self):
        from unittest.mock import patch
        meta = self.legacy_prepared()
        folder = self.report(meta)
        before = {p: p.read_bytes() for p in self.terminal.rglob('*') if p.is_file()}
        with patch.object(session, 'terminal_processes', return_value=[]):
            self.assertEqual(session.main(['configure-profile', '--session-dir', str(self.directory)]), 0)
        upgraded = session.load_prepared(self.directory)
        for key in ('magic', 'nonce', 'presets', 'created_at'):
            self.assertEqual(upgraded[key], meta[key])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse((self.directory / 'stage-verified.json').exists())
        self.assertEqual((self.directory / 'session.json').stat().st_mode & 0o777, 0o600)
        for name in ('PREFLIGHT', 'STAGE', 'RUN'):
            self.assertIn('ProfileLast=' + upgraded['profile_name'], (self.directory / (name + '.ini')).read_text())
        self.assertTrue(folder.is_dir())

    def test_upgrade_refuses_receipt_activation_or_modified_pins(self):
        from unittest.mock import patch
        meta = self.legacy_prepared()
        original = (self.directory / 'session.json').read_bytes()
        with patch.object(session, 'terminal_processes', return_value=[]):
            for name in ('stage-verified.json', 'ACTIVATE_SERVER_DEMO20'):
                marker = self.directory / name
                marker.write_text('fixture')
                with self.assertRaises(session.GuardError):
                    session.configure_profile(self.directory)
                marker.unlink()
            Path(meta['presets']['stage']).write_text('tampered')
            with self.assertRaises(session.GuardError):
                session.configure_profile(self.directory)
        self.assertEqual(original, (self.directory / 'session.json').read_bytes())

    def test_owned_profile_archive_preserves_all_nonprofile_state(self):
        meta = self.prepare()
        profile = Path(meta['profile_dir'])
        profile.mkdir(parents=True)
        (profile / 'chart01.chr').write_bytes(b'old disabled stage chart')
        others = [profile.parent / 'Default/chart.chr', self.terminal / 'Bases/gvariables.dat',
                  self.terminal / 'Config/common.ini', self.terminal / 'MQL5/Files/GoldShield/state.lock']
        for path in others:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'preserve ' + path.name.encode())
        before = {p: p.read_bytes() for p in others}
        session.launch_argv(self.directory, 'stage', str, [])
        self.assertTrue((profile / 'chart01.chr').exists(), 'argv must be pure')
        session.prepare_owned_profile(self.directory)
        self.assertEqual(list(profile.iterdir()), [])
        self.assertEqual(profile.stat().st_mode & 0o777, 0o700)
        archives = list((self.directory / 'profile-backups').glob('*/chart01.chr'))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_bytes(), b'old disabled stage chart')
        self.assertEqual(before, {p: p.read_bytes() for p in others})
        self.assertEqual((self.directory / 'profile-backups').stat().st_mode & 0o777, 0o700)

    def test_profile_rejects_bad_paths_symlinks_nondirs_and_ambiguity(self):
        meta = self.prepare()
        profile = Path(meta['profile_dir'])
        profile.parent.mkdir(parents=True)
        for value in (str(self.root / 'outside'), str(profile / '..'), str(profile.parent / 'Default')):
            with self.subTest(value=value), self.assertRaises(session.GuardError):
                session.prepare_owned_profile(dict(meta, profile_dir=value))
        outside = self.root / 'outside'
        outside.mkdir()
        profile.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(session.GuardError):
            session.prepare_owned_profile(meta)
        profile.unlink(); profile.write_text('not directory')
        with self.assertRaises(session.GuardError):
            session.prepare_owned_profile(meta)
        profile.unlink()
        charts = profile.parent
        charts.rmdir(); charts.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(session.GuardError):
            session.prepare_owned_profile(meta)
        charts.unlink(); charts.mkdir()
        (charts.parent / 'charts').mkdir()
        with self.assertRaises(session.GuardError):
            session.prepare_owned_profile(meta)

    def test_launch_prepares_profile_only_after_all_guards(self):
        from unittest.mock import patch
        meta = self.prepare()
        profile = Path(meta['profile_dir'])
        profile.mkdir(parents=True)
        chart = profile / 'saved.chr'
        chart.write_text('saved')
        with patch.object(session, 'terminal_processes', return_value=['terminal64.exe']), patch.object(session.os, 'execvpe') as execute:
            with self.assertRaises(SystemExit):
                session.main(['launch', '--session-dir', str(self.directory), '--mode', 'stage'])
            execute.assert_not_called()
        self.assertTrue(chart.exists())
        with patch.object(session, 'terminal_processes', return_value=[]), patch.object(session, 'windows_path', side_effect=str), patch.object(session.os, 'execvpe') as execute:
            session.main(['launch', '--session-dir', str(self.directory), '--mode', 'stage'])
            execute.assert_called_once()
        self.assertFalse(chart.exists())

    def report(self, meta, **changes):
        folder = self.terminal / 'MQL5/Files/GoldShield'
        folder.mkdir(parents=True, exist_ok=True)
        key = session.audit_key('Exness-MT5Trial7', '12345', meta['magic'])
        (folder / (key + '.lock')).write_bytes(b'\x01\x00\x00\x00')
        bases = self.terminal / 'Bases'
        bases.mkdir(exist_ok=True)
        (bases / 'gvariables.dat').write_bytes(b'fixture native persistence')
        row = dict(zip(session.CSV_FIELDS, [''] * len(session.CSV_FIELDS)))
        row.update(nonce=meta['nonce'], connected='1', account_mode='ACCOUNT_TRADE_MODE_DEMO',
                   margin_mode='ACCOUNT_MARGIN_MODE_RETAIL_HEDGING', server='Exness-MT5Trial7',
                   currency='USD', login='12345', symbol='XAUUSDm', balance='1000', equity='1000',
                   positions_total='0', orders_total='0', account_trade_allowed='1', account_expert_allowed='1',
                   terminal_trade_allowed='0', magic=str(meta['magic']), audit_key=key, store_schema='1',
                   reference='1000', trial_schema='1', entry_submissions='0', limit='20', blocked='0', pending='0',
                   history_available='1', matching_history_deals='0', namespace_present='1')
        row.update(changes)
        with (folder / 'server_preflight.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=session.CSV_FIELDS)
            writer.writeheader(); writer.writerow(row)
        with (folder / f"demo20_{meta['magic']}.csv").open('w', newline='') as stream:
            snapshot = dict(account_mode='DEMO', symbol='XAUUSDm', limit='20', entry_submissions='0',
                            open_positions='0', trial_status='RUNNING_WAIT_VALID_SIGNAL', core_state='READY', core_reason='NONE')
            writer = csv.DictWriter(stream, fieldnames=list(snapshot))
            writer.writeheader(); writer.writerow(snapshot)
        return folder

    def test_stage_verifies_real_files_and_binds_run_login(self):
        self.assertTrue(hasattr(session, 'verify_stage'), 'stage verification missing')
        meta = self.prepare()
        self.report(meta)
        receipt = session.verify_stage(self.directory)
        self.assertEqual(receipt['status'], 'FRESH_SERVER_DEMO20_STAGE_VERIFIED')
        self.assertEqual(receipt['identity']['login'], '12345')
        self.assertIn('Login=12345', (self.directory / 'RUN.ini').read_text())
        self.assertIn('KeepPrivate=1\n', (self.directory / 'RUN.ini').read_text())
        self.assertIn('KeepPrivate=1\n', session.config('active.set', 'probe.set', True, login='12345'))
        self.assertNotIn('Password=', (self.directory / 'RUN.ini').read_text())
        self.assertTrue((self.directory / 'stage-verified.json').is_file())

    def readonly_report(self, meta, **changes):
        import sys
        missing = str(sys.float_info.max)
        values = dict(namespace_present='0', store_schema=missing, trial_schema=missing,
                      reference=missing, entry_submissions=missing, limit=missing, blocked=missing, pending=missing)
        values.update(changes)
        folder = self.report(meta, **values)
        for marker in folder.glob('*.lock'):
            marker.unlink()  # Synthetic fixture only, not a real terminal.
        (folder / f"demo20_{meta['magic']}.csv").unlink()
        return folder / 'server_preflight.csv'

    def test_native_preflight_binds_saved_account_to_all_configs_without_duplicate_sections(self):
        self.assertTrue(hasattr(session, 'bind_preflight'), 'saved-account preflight binding missing')
        meta = self.prepare()
        report = self.readonly_report(meta)
        globals_path = self.terminal / 'Bases/gvariables.dat'
        native_before = globals_path.read_bytes()
        bound = session.bind_preflight(self.directory, report)
        self.assertEqual((bound['nonce'], bound['magic']), (meta['nonce'], meta['magic']))
        self.assertEqual(bound['expected_login'], '12345')
        self.assertEqual(globals_path.read_bytes(), native_before)
        for label in ('PREFLIGHT', 'STAGE', 'RUN'):
            value = (self.directory / (label + '.ini')).read_text()
            self.assertEqual(value.count('[Common]'), 1)
            self.assertIn('Login=12345', value)
            self.assertIn('KeepPrivate=1', value)
        session.load_prepared(self.directory)
        self.report(bound)
        session.verify_stage(self.directory)
        self.assertEqual((self.directory / 'RUN.ini').read_text().count('[Common]'), 1)

    def test_preflight_binding_rejects_wrong_identity_existing_namespace_and_activated_session(self):
        self.assertTrue(hasattr(session, 'bind_preflight'), 'saved-account preflight binding missing')
        meta = self.prepare()
        for values in ({'account_mode':'ACCOUNT_TRADE_MODE_REAL'}, {'nonce':'wrong'}, {'connected':'0'},
                       {'positions_total':'1'}, {'namespace_present':'1'}, {'matching_history_deals':'1'}):
            report = self.readonly_report(meta, **values)
            with self.assertRaises(session.GuardError):
                session.bind_preflight(self.directory, report)
            self.assertNotIn('expected_login', session.load_prepared(self.directory))
        report = self.readonly_report(meta)
        (self.directory / 'ACTIVATE_SERVER_DEMO20').write_text(meta['nonce'])
        with self.assertRaises(session.GuardError):
            session.bind_preflight(self.directory, report)

    def test_config_upgrade_after_account_binding_disables_terminal_without_resetting_state(self):
        meta = self.prepare()
        report = self.readonly_report(meta)
        bound = session.bind_preflight(self.directory, report)
        stage = self.directory / 'STAGE.ini'
        stage.write_text(stage.read_text().replace('Enabled=0', 'Enabled=1'))
        bound['hashes'][str(stage)] = session.digest(stage)
        (self.directory / 'session.json').write_text(json.dumps(bound))
        native = self.terminal / 'Bases/gvariables.dat'
        before = native.read_bytes()
        upgraded = session.configure_profile(self.directory)
        self.assertIn('\nEnabled=0\n', stage.read_text())
        self.assertIn('Login=12345', stage.read_text())
        self.assertEqual(stage.read_text().count('[Charts]'), 1)
        self.assertEqual(native.read_bytes(), before)
        self.assertEqual((upgraded['magic'], upgraded['nonce']), (meta['magic'], meta['nonce']))

    def test_stage_requires_terminal_autotrading_off(self):
        meta = self.prepare()
        self.report(meta, terminal_trade_allowed='1')
        with self.assertRaises(session.GuardError):
            session.verify_stage(self.directory)
        self.report(meta, terminal_trade_allowed='0')
        receipt = session.verify_stage(self.directory)
        self.assertEqual(receipt['status'], 'FRESH_SERVER_DEMO20_STAGE_VERIFIED')

    def test_native_probe_never_prompts_for_inputs(self):
        source = (ROOT / 'tools/mql5/GoldShield_ServerPreflight.mq5').read_text()
        self.assertNotIn('#property script_show_inputs', source)

    def test_missing_native_reference_sentinel_is_rejected(self):
        import sys
        meta = self.prepare()
        self.report(meta, reference=str(sys.float_info.max))
        with self.assertRaises(session.GuardError):
            session.verify_stage(self.directory)

    def test_native_preflight_reports_history_and_namespace(self):
        source = (ROOT / 'tools/mql5/GoldShield_ServerPreflight.mq5').read_text()
        self.assertIn('HistorySelect(', source)
        self.assertIn('matching_history_deals', source)
        self.assertIn('namespace_present', source)
        self.assertIn('GlobalVariablesTotal()', source)

    def test_prepare_guards(self):
        for magic in (0, -1, 2**53, 2611061815392):
            with self.subTest(magic=magic), self.assertRaises(session.GuardError):
                session.prepare(self.directory, self.terminal, magic)
        target = self.terminal / 'MQL5/Experts/GoldShield_DEMO20.ex5'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'modified')
        with self.assertRaises(session.GuardError):
            self.prepare()

    def test_stage_rejects_unsafe_report(self):
        self.assertTrue(hasattr(session, 'verify_stage'), 'stage verification missing')
        meta = self.prepare()
        cases = [dict(account_mode='ACCOUNT_TRADE_MODE_REAL'), dict(server='Other'), dict(nonce='wrong'),
                 dict(balance='nan'), dict(equity='inf'), dict(reference='0'), dict(positions_total='1'),
                 dict(orders_total='1'), dict(blocked='1'), dict(pending='1'), dict(entry_submissions='1'),
                 dict(audit_key='GS2.0000000000000000'), dict(connected='0'), dict(margin_mode='NETTING'),
                 dict(history_available='0'), dict(matching_history_deals='1'), dict(namespace_present='0')]
        for changes in cases:
            with self.subTest(changes=changes):
                self.report(meta, **changes)
                with self.assertRaises(session.GuardError):
                    session.verify_stage(self.directory)
                self.assertFalse((self.directory / 'stage-verified.json').exists())
        folder = self.report(meta)
        os.utime(folder / 'server_preflight.csv', (time.time()-121, time.time()-121))
        with self.assertRaises(session.GuardError):
            session.verify_stage(self.directory)
        self.report(meta)
        (self.terminal / 'Bases/gvariables.dat').unlink()
        with self.assertRaises(session.GuardError):
            session.verify_stage(self.directory)
        folder = self.report(meta)
        next(folder.glob('*.lock')).unlink()
        with self.assertRaises(session.GuardError):
            session.verify_stage(self.directory)

    def test_launch_gates_resume_and_argv(self):
        self.assertTrue(hasattr(session, 'launch_argv'), 'launcher behavior missing')
        meta = self.prepare()
        convert = lambda p: 'Z:\\fixture\\' + p.name
        self.assertIn('/portable', session.launch_argv(self.directory, 'stage', convert, []))
        with self.assertRaises(session.GuardError):
            session.launch_argv(self.directory, 'run', convert, [])
        folder = self.report(meta)
        session.verify_stage(self.directory)
        with self.assertRaises(session.GuardError):
            session.launch_argv(self.directory, 'run', convert, [])
        (self.directory / 'ACTIVATE_SERVER_DEMO20').write_text(meta['nonce'])
        # Stale probes and nonzero/open final position must not prevent management on restart.
        (folder / 'server_preflight.csv').unlink()
        (folder / f"demo20_{meta['magic']}.csv").write_text('entry_submissions,open_positions\n20,1\n')
        before = (self.terminal / 'Bases/gvariables.dat').read_bytes()
        argv = session.launch_argv(self.directory, 'run', convert, [])
        self.assertEqual(argv[0], 'wine')
        self.assertTrue(argv[-1].startswith('/config:Z:'))
        self.assertEqual(before, (self.terminal / 'Bases/gvariables.dat').read_bytes())
        with self.assertRaises(session.GuardError):
            session.launch_argv(self.directory, 'run', convert, ['C:\\terminal64.exe'])
        Path(meta['presets']['active']).write_text('tampered')
        with self.assertRaises(session.GuardError):
            session.launch_argv(self.directory, 'run', convert, [])

    def test_native_script_and_unit_readonly_contract(self):
        path = ROOT / 'tools/mql5/GoldShield_ServerPreflight.mq5'
        self.assertTrue(path.is_file(), 'native script missing')
        source = path.read_text()
        for forbidden in ('OrderSend', 'GlobalVariableSet', '#import', '#include', 'PositionClose', 'WebRequest'):
            self.assertNotIn(forbidden, source)
        for required in ('ProbeMagic', 'RequestId', 'WaitForState', 'server_preflight.csv', 'FileFlush', 'FileClose', '2166136261', '5381'):
            self.assertIn(required, source)
        service = (ROOT / 'deployment/server-demo/goldshield-server-demo.service').read_text()
        self.assertIn('MemoryHigh=1400M', service)
        self.assertIn('MemoryMax=1800M', service)
        self.assertIn('Restart=always', service)
        self.assertIn('${GOLDSHIELD_SESSION_DIR}', service)
        meta = self.prepare()
        for name in ('STAGE', 'RUN'):
            content = (self.directory / (name + '.ini')).read_text()
            self.assertIn('Account=1', content)
            self.assertIn('Profile=1', content)

    def test_native_numeric_rendering_and_script_only_preflight(self):
        meta = self.prepare()
        self.assertTrue((self.directory / 'PREFLIGHT.ini').exists(), 'script-only preflight missing')
        text = (self.directory / 'PREFLIGHT.ini').read_text()
        self.assertIn('Enabled=0', text)
        self.assertNotIn('Expert=GoldShield', text)
        self.assertIn('WaitForState=false', Path(meta['presets']['preflight_probe']).read_text())
        self.report(meta, store_schema='1.0', trial_schema='1.0', pending='0.0', blocked='0.0',
                    entry_submissions='0.0', limit='20.0')
        session.verify_stage(self.directory)

    def test_source_hash_flags_overwrite_and_blocked_snapshot_guards(self):
        from unittest.mock import patch
        import shutil
        bundle = self.root / 'bundle'
        shutil.copytree(session.BUNDLE, bundle)
        preset = bundle / 'presets/DEMO20_CURRENT.set'
        with patch.object(session, 'BUNDLE', bundle):
            preset.write_text(preset.read_text().replace('AllowRealTrading=false', 'AllowRealTrading=true'))
            with self.assertRaises(session.GuardError):
                self.prepare()
            manifest_path = bundle / 'bundle-manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['files']['presets/DEMO20_CURRENT.set'] = session.digest(preset)
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(session.GuardError):
                self.prepare()
        meta = self.prepare()
        folder = self.report(meta)
        snapshot = folder / f"demo20_{meta['magic']}.csv"
        snapshot.write_text(snapshot.read_text().replace('READY', 'ERROR_BLOCKED'))
        with self.assertRaises(session.GuardError):
            session.verify_stage(self.directory)
        self.report(meta)
        Path(meta['presets']['stage']).write_text('modified')
        with self.assertRaises(session.GuardError):
            session.verify_stage(self.directory)


if __name__ == '__main__':
    unittest.main()
