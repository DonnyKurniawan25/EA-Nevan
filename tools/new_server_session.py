#!/usr/bin/env python3
"""Separate FRESH_SERVER_DEMO20 bootstrap; never imports or edits terminal state.

Native report: MQL5/Files/GoldShield/server_preflight.csv (CSV_FIELDS below).
Persistent evidence: GoldShield/<audit_key>.lock and [Bb]ases/gvariables.dat.
The operator must compile/install GoldShield_ServerPreflight.ex5 separately.
"""
import argparse
import configparser
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'deployment/linux-guide'
MAX_MAGIC = 2**53 - 1
AUTHORIZATION = 'Owner 1227557858 authorized NEW server DEMO20; PC EA disabled; no PC state migration.'


class GuardError(RuntimeError):
    """Fail closed without reporting private account details."""


def require(condition, reason):
    if not condition:
        raise GuardError(reason)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_set(path):
    result = {}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith(';'):
            continue
        key, value = line.split('=', 1)
        require(key.strip() not in result, 'duplicate preset field')
        result[key.strip()] = value.strip()
    return result


def write_new(path, content):
    path = Path(path)
    with path.open('x', encoding='utf-8', newline='') as stream:
        os.chmod(path, 0o600)
        stream.write(content)


def write_json(path, data):
    write_new(path, json.dumps(data, indent=2, sort_keys=True) + '\n')


def config(preset, probe, live, login=None, symbol='XAUUSDm'):
    common = '' if login is None else f'[Common]\nLogin={login}\nServer=Exness-MT5Trial7\nKeepPrivate=1\n'
    return (common + '[Experts]\nEnabled=' + str(int(live)) + '\nAllowLiveTrading=' + str(int(live)) +
            '\nAllowDllImport=0\nAccount=1\nProfile=1\n[StartUp]\nExpert=GoldShield_DEMO20\nExpertParameters=' +
            preset + f'\nSymbol={symbol}\nPeriod=M15\nScript=GoldShield_ServerPreflight\nScriptParameters=' + probe + '\n')


def profile_location(meta):
    directory = Path(meta['session_dir'])
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', directory.name), 'unsafe session name')
    require(re.fullmatch(r'[a-f0-9]{64}', meta['nonce']), 'invalid session nonce')
    terminal = Path(meta['terminal_dir'])
    require(terminal.is_absolute() and terminal.resolve() == terminal and terminal.is_dir(), 'unsafe terminal path')
    root = terminal
    for component in ('MQL5', 'Profiles', 'Charts'):
        matches = [p for p in root.iterdir() if p.name.lower() == component.lower()] if root.exists() else []
        require(len(matches) <= 1, 'ambiguous profile root')
        root = matches[0] if matches else root / component
        require(not root.is_symlink() and (not root.exists() or root.is_dir()), 'unsafe profile root')
    name = 'GS_Server_' + directory.name + '_' + meta['nonce'][:8]
    profile = root / name
    require(not profile.is_symlink() and (not profile.exists() or profile.is_dir()), 'unsafe owned profile')
    require(profile.resolve().parent == root.resolve(), 'profile escaped chart root')
    return name, profile


def prepare(session_dir, terminal_dir, magic=None, symbol='XAUUSDm', base_preset=None, login=None):
    directory, terminal = Path(session_dir).absolute(), Path(terminal_dir).resolve()
    require(not directory.exists(), 'session directory already exists')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', directory.name), 'unsafe session name')
    require(terminal.is_dir(), 'terminal directory missing')
    manifest = json.loads((BUNDLE / 'bundle-manifest.json').read_text())
    source = BUNDLE / 'Experts/GoldShield_DEMO20.ex5'
    preset_rel = 'presets/' + (base_preset if base_preset else ('DEMO20_BTCUSDm.set' if symbol == 'BTCUSDm' else 'DEMO20_CURRENT.set'))
    base = BUNDLE / preset_rel
    for file, relative in ((source, 'Experts/GoldShield_DEMO20.ex5'), (base, preset_rel)):
        require(digest(file) == manifest['files'][relative], 'source bundle hash mismatch')
    fields = parse_set(base)
    expected = {'ExecutionMode': '2', 'EnableAutoTrading': 'true', 'DemoTradingOptIn': 'true',
                'AllowRealTrading': 'false', 'TradeSymbol': symbol, 'SignalTimeframe': '15',
                'GridEnabled': 'false', 'ApiEnabled': 'false', 'TelegramEnabled': 'false',
                'RequiredAccountCurrency': 'USD'}
    require(all(fields.get(k) == v for k, v in expected.items()), 'unsafe base flags')
    old_magic = int(fields['MagicNumber'])
    if magic is None:
        magic = secrets.randbelow(MAX_MAGIC) + 1
        while magic == old_magic:
            magic = secrets.randbelow(MAX_MAGIC) + 1
    require(type(magic) is int and 0 < magic <= MAX_MAGIC and magic != old_magic, 'invalid or old magic')
    preset_dir = terminal / 'MQL5/Presets/GoldShieldServer' / directory.name
    require(not preset_dir.exists(), 'preset directory already exists')
    target = terminal / 'MQL5/Experts/GoldShield_DEMO20.ex5'
    require(not target.exists() or digest(target) == digest(source), 'terminal binary mismatch')
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    preset_dir.mkdir(parents=True, mode=0o700)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)
    nonce = secrets.token_hex(32)
    profile_name, profile_dir = profile_location({'session_dir': str(directory), 'terminal_dir': str(terminal), 'nonce': nonce})
    chart_config = '[Charts]\nProfileLast=' + profile_name + '\n'
    account_prefix = '' if login is None else f'[Common]\nLogin={login}\nServer=Exness-MT5Trial7\nKeepPrivate=1\n'
    presets = {}
    for name, enabled in (('stage', False), ('active', True)):
        values = dict(fields, MagicNumber=str(magic), EnableAutoTrading=str(enabled).lower(), DemoTradingOptIn=str(enabled).lower())
        path = preset_dir / (name + '.set')
        write_new(path, ''.join(k + '=' + v + '\n' for k, v in values.items()))
        presets[name] = str(path)
    probe = preset_dir / 'probe.set'
    write_new(probe, f'ProbeMagic={magic}\nRequestId={nonce}\nWaitForState=true\n')
    presets['probe'] = str(probe)
    preflight_probe = preset_dir / 'preflight-probe.set'
    write_new(preflight_probe, f'ProbeMagic={magic}\nRequestId={nonce}\nWaitForState=false\n')
    presets['preflight_probe'] = str(preflight_probe)
    rel = 'GoldShieldServer\\' + directory.name + '\\'
    write_new(directory / 'PREFLIGHT.ini', account_prefix + chart_config + '[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\nAccount=1\nProfile=1\n[StartUp]\nSymbol=' + symbol + '\nPeriod=M15\nScript=GoldShield_ServerPreflight\nScriptParameters=' + rel + 'preflight-probe.set\n')
    for name, live in (('STAGE', False), ('RUN', True)):
        write_new(directory / (name + '.ini'), chart_config + config(rel + ('active.set' if live else 'stage.set'), rel + 'probe.set', live, login=login, symbol=symbol))
    paths = [target, directory / 'PREFLIGHT.ini', directory / 'STAGE.ini', directory / 'RUN.ini'] + [Path(p) for p in presets.values()]
    meta = {'status': 'FRESH_SERVER_DEMO20', 'authorization_reason': AUTHORIZATION, 'nonce': nonce,
            'symbol': symbol,
            'magic': magic, 'old_magic': old_magic, 'terminal_dir': str(terminal), 'session_dir': str(directory),
            'profile_name': profile_name, 'profile_dir': str(profile_dir),
            'created_at': time.time(), 'presets': presets, 'hashes': {str(p): digest(p) for p in paths}}
    if login is not None:
        meta['expected_login'] = str(login)
    write_json(directory / 'session.json', meta)
    return meta


CSV_FIELDS = ('nonce connected account_mode margin_mode server currency login symbol balance equity '
              'positions_total orders_total account_trade_allowed account_expert_allowed terminal_trade_allowed '
              'magic audit_key store_schema reference trial_schema entry_submissions limit blocked pending '
              'history_available matching_history_deals namespace_present').split()


def audit_key(server, login, magic, symbol='XAUUSDm'):
    identity = f'{server}|{login}|{symbol}|{magic}'
    a, b = 2166136261, 5381
    # MQL StringGetCharacter hashes UTF-16 code units, not UTF-8 bytes.
    encoded = identity.encode('utf-16-le')
    for index in range(0, len(encoded), 2):
        ch = int.from_bytes(encoded[index:index + 2], 'little')
        a = ((a ^ ch) * 16777619) & 0xffffffff
        b = ((b * 33) ^ ch) & 0xffffffff
    return f'GS2.{a:08X}{b:08X}'


def validate_hashes(hashes):
    require(isinstance(hashes, dict) and bool(hashes), 'missing file pins')
    for path, expected in hashes.items():
        require(Path(path).is_file() and digest(path) == expected, 'pinned file changed or missing')


def load_prepared(directory):
    directory = Path(directory).resolve()
    meta = json.loads((directory / 'session.json').read_text())
    require(meta['status'] == 'FRESH_SERVER_DEMO20' and meta['session_dir'] == str(directory), 'wrong session metadata')
    require(re.fullmatch('[a-f0-9]{64}', meta['nonce']), 'invalid session nonce')
    require(0 < meta['magic'] <= MAX_MAGIC and meta['magic'] != meta['old_magic'], 'invalid session magic')
    validate_hashes(meta['hashes'])
    return meta


def configure_profile(session_dir):
    directory = Path(session_dir).resolve()
    require(not any((directory / name).exists() or (directory / name).is_symlink()
                    for name in ('stage-verified.json', 'ACTIVATE_SERVER_DEMO20')), 'session already verified or activated')
    meta = load_prepared(directory)
    require(not terminal_processes(), 'another terminal64 process exists for this user')
    name, profile = profile_location(meta)
    updates = []
    for label in ('PREFLIGHT', 'STAGE', 'RUN'):
        path = directory / (label + '.ini')
        require(str(path) in meta['hashes'] and not path.is_symlink(), 'config not pinned')
        original = path.read_text()
        parsed = configparser.ConfigParser(interpolation=None, strict=True)
        parsed.optionxform = lambda optionstr: optionstr
        parsed.read_string(original)
        require(not parsed.has_section('Charts') or parsed.get('Charts', 'ProfileLast', fallback='') == name,
                'unexpected chart config')
        if not parsed.has_section('Charts'):
            parsed.add_section('Charts')
        parsed.set('Charts', 'ProfileLast', name)
        if label == 'STAGE':
            require(parsed.get('Experts', 'AllowLiveTrading') == '0', 'unsafe stage trading permission')
            parsed.set('Experts', 'Enabled', '0')
        rendered = io.StringIO()
        parsed.write(rendered, space_around_delimiters=False)
        updates.append((path, rendered.getvalue()))
    for path, content in updates:
        temporary = path.with_suffix('.profile-new')
        write_new(temporary, content)
        temporary.replace(path)
        meta['hashes'][str(path)] = digest(path)
    meta.update(profile_name=name, profile_dir=str(profile))
    temporary = directory / 'session.profile-new.json'
    write_json(temporary, meta)
    temporary.replace(directory / 'session.json')
    return meta


def prepare_owned_profile(meta_or_session_dir):
    """Archive only owned UI charts; never touch the EA's persistent state."""
    meta = meta_or_session_dir if isinstance(meta_or_session_dir, dict) else load_prepared(meta_or_session_dir)
    name, profile = profile_location(meta)
    require(meta.get('profile_name') == name and meta.get('profile_dir') == str(profile), 'profile binding mismatch')
    directory = Path(meta['session_dir'])
    require(directory.is_absolute() and directory.resolve() == directory and directory.is_dir(), 'unsafe session path')
    backups = directory / 'profile-backups'
    require(not backups.is_symlink() and (not backups.exists() or backups.is_dir()), 'unsafe profile backups')
    backups.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backups, 0o700)
    if profile.exists():
        destination = backups / (name + '-' + secrets.token_hex(16))
        require(not destination.exists() and not destination.is_symlink(), 'profile backup collision')
        profile.rename(destination)
        os.chmod(destination, 0o700)
    profile.mkdir(parents=True, mode=0o700)
    os.chmod(profile, 0o700)
    return profile


def one_row(path, expected=None):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        require(expected is None or reader.fieldnames == expected, 'wrong CSV schema')
        rows = list(reader)
    require(len(rows) == 1 and None not in rows[0] and all(v is not None for v in rows[0].values()), 'CSV must contain exactly one complete row')
    return rows[0]


def pin_account_config(text, login):
    require(re.fullmatch(r'[1-9][0-9]*', login), 'invalid saved account selection')
    rest = re.sub(r'(?ms)^\[Common\]\r?\n.*?(?=^\[|\Z)', '', text)
    return '[Common]\nLogin=' + login + '\nServer=Exness-MT5Trial7\nKeepPrivate=1\n' + rest


def bind_preflight(session_dir, report_path):
    """Select cached credentials from prior native evidence, not current authorization.

    Evidence can be retained across a stopped terminal. STAGE must still produce
    a NEW fresh report before verification; no password or MT5 state is read/edited.
    """
    directory = Path(session_dir).resolve()
    require(not any((directory / n).exists() or (directory / n).is_symlink()
                    for n in ('stage-verified.json', 'ACTIVATE_SERVER_DEMO20')), 'session already verified or activated')
    meta = load_prepared(directory)
    require(not terminal_processes(), 'another terminal64 process exists for this user')
    row = one_row(report_path, CSV_FIELDS)
    symbol = meta.get('symbol', 'XAUUSDm')
    expected = {'nonce': meta['nonce'], 'magic': str(meta['magic']), 'connected': '1',
                'account_mode': 'ACCOUNT_TRADE_MODE_DEMO', 'margin_mode': 'ACCOUNT_MARGIN_MODE_RETAIL_HEDGING',
                'server': 'Exness-MT5Trial7', 'currency': 'USD', 'symbol': symbol,
                'positions_total': '0', 'orders_total': '0', 'account_trade_allowed': '1',
                'account_expert_allowed': '1', 'terminal_trade_allowed': '0', 'history_available': '1',
                'matching_history_deals': '0', 'namespace_present': '0'}
    require(all(row.get(k) == v for k, v in expected.items()), 'readonly preflight binding rejected')
    require(re.fullmatch(r'[1-9][0-9]*', row['login']), 'invalid account identity')
    require(meta.get('expected_login', row['login']) == row['login'], 'cannot change bound account')
    for name in ('balance', 'equity'):
        value = float(row[name])
        require(math.isfinite(value) and 0 < value < sys.float_info.max, 'invalid preflight account')
    symbol = meta.get('symbol', 'XAUUSDm')
    key = audit_key(row['server'], row['login'], meta['magic'], symbol=symbol)
    require(row['audit_key'] == key, 'preflight prefix mismatch')
    folder = Path(meta['terminal_dir']) / 'MQL5/Files/GoldShield'
    require(not (folder / (key + '.lock')).exists() and
            not (folder / f"demo20_{meta['magic']}.csv").exists(), 'namespace already initialized')
    for label in ('PREFLIGHT', 'STAGE', 'RUN'):
        path = directory / (label + '.ini')
        require(str(path) in meta['hashes'] and not path.is_symlink(), 'config not pinned')
        temporary = path.with_suffix('.account-new')
        write_new(temporary, pin_account_config(path.read_text(), row['login']))
        temporary.replace(path)
        meta['hashes'][str(path)] = digest(path)
    meta.update(expected_login=row['login'], expected_audit_key=key,
                preflight_report_sha256=digest(report_path))
    temporary = directory / 'session.account-new.json'
    write_json(temporary, meta)
    temporary.replace(directory / 'session.json')
    return meta


def persistent_files(meta, key):
    terminal = Path(meta['terminal_dir'])
    lock = terminal / 'MQL5/Files/GoldShield' / (key + '.lock')
    bases = [p for p in terminal.iterdir() if p.is_dir() and p.name.lower() == 'bases']
    globals_files = [p for base in bases for p in base.rglob('*') if p.name.lower() == 'gvariables.dat' and p.is_file()]
    require(lock.is_file() and lock.stat().st_size > 0, 'native lock missing or empty')
    require(len(globals_files) == 1 and globals_files[0].stat().st_size > 0, 'native persistent globals missing or ambiguous')
    return [lock, globals_files[0]]


def file_identity(path):
    stat = Path(path).stat()
    return {'path': str(path), 'device': stat.st_dev, 'inode': stat.st_ino}


def verify_stage(session_dir, now=None):
    directory = Path(session_dir).resolve()
    require(not (directory / 'stage-verified.json').exists(), 'session already verified')
    meta = load_prepared(directory)
    folder = Path(meta['terminal_dir']) / 'MQL5/Files/GoldShield'
    report = folder / 'server_preflight.csv'
    now = time.time() if now is None else now
    require(report.is_file() and 0 <= now - report.stat().st_mtime <= 120, 'stale or missing report')
    row = one_row(report, CSV_FIELDS)
    symbol = meta.get('symbol', 'XAUUSDm')
    expected = {'nonce': meta['nonce'], 'account_mode': 'ACCOUNT_TRADE_MODE_DEMO',
                'margin_mode': 'ACCOUNT_MARGIN_MODE_RETAIL_HEDGING', 'server': 'Exness-MT5Trial7',
                'currency': 'USD', 'symbol': symbol, 'magic': str(meta['magic'])}
    require(all(row.get(k) == v for k, v in expected.items()), 'native report identity mismatch')
    require(re.fullmatch('[1-9][0-9]*', row['login']), 'invalid account identity')
    require(meta.get('expected_login', row['login']) == row['login'], 'stage account differs from readonly preflight')
    for field in ('balance', 'equity', 'reference'):
        value = float(row[field])
        require(math.isfinite(value) and 0 < value < sys.float_info.max, 'invalid native financial field')
    for field in ('connected', 'account_trade_allowed', 'account_expert_allowed', 'store_schema', 'trial_schema'):
        require(float(row[field]) == 1, 'native permission or schema rejected')
    require(float(row['terminal_trade_allowed']) == 0, 'stage terminal autotrading must be disabled')
    require(row['history_available'] == '1' and float(row['matching_history_deals']) == 0 and
            row['namespace_present'] == '1', 'fresh namespace or broker history rejected')
    for field in ('positions_total', 'orders_total', 'entry_submissions', 'blocked', 'pending'):
        require(float(row[field]) == 0, 'stage must be fresh flat unblocked state')
    require(float(row['limit']) == 20, 'trial cap mismatch')
    key = audit_key(row['server'], row['login'], meta['magic'], symbol=symbol)
    require(re.fullmatch(r'GS2\.[0-9A-F]{16}', row['audit_key']) and row['audit_key'] == key, 'native audit key mismatch')
    persistent = persistent_files(meta, key)
    snapshot = one_row(folder / f"demo20_{meta['magic']}.csv")
    for k, v in {'account_mode': 'DEMO', 'symbol': symbol, 'limit': '20', 'entry_submissions': '0', 'open_positions': '0'}.items():
        require(snapshot.get(k) == v, 'trial snapshot mismatch')
    status = '|'.join(snapshot.values()).upper()
    require(not any(token in status for token in ('ERROR_BLOCKED', 'PAUSED_RISK', 'HISTORY_UNAVAILABLE')), 'trial snapshot blocked')
    require(snapshot.get('trial_status') == 'RUNNING_WAIT_VALID_SIGNAL', 'trial snapshot not ready')
    # Finalize account pin before sealing hashes. No password is ever written.
    run = directory / 'RUN.ini'
    original = run.read_text()
    with run.open('w', encoding='utf-8') as stream:
        stream.write(pin_account_config(original, row['login']))
    os.chmod(run, 0o600)
    meta['hashes'][str(run)] = digest(run)
    # Atomic private metadata replacement; not a terminal-state mutation.
    temporary = directory / 'session.finalizing.json'
    write_json(temporary, meta)
    temporary.replace(directory / 'session.json')
    receipt = {'status': 'FRESH_SERVER_DEMO20_STAGE_VERIFIED', 'nonce': meta['nonce'], 'magic': meta['magic'],
               'verified_at': now, 'identity': {k: row[k] for k in ('login', 'server', 'currency', 'account_mode', 'margin_mode', 'symbol')},
               'reference': row['reference'], 'audit_key': key, 'hashes': dict(meta['hashes']),
               'metadata_hash': digest(directory / 'session.json'), 'persistent': [file_identity(p) for p in persistent],
               'native_report_sha256': digest(report)}
    write_json(directory / 'stage-verified.json', receipt)
    return receipt


def terminal_processes():
    processes = []
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            command = (process / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if re.search(r'(?:^|[ /\\])terminal64\.exe(?: |$)', command, re.IGNORECASE):
                processes.append(command)
        except FileNotFoundError:
            continue
    return processes


def windows_path(path):
    result = subprocess.run(['winepath', '-w', str(path)], check=True, capture_output=True, text=True)
    value = result.stdout.strip()
    require(bool(value) and '\n' not in value, 'winepath conversion failed')
    return value


def launch_argv(session_dir, mode, converter=None, processes=None):
    require(mode in ('stage', 'run'), 'invalid launch mode')
    directory = Path(session_dir).resolve()
    meta = load_prepared(directory)
    require(not (terminal_processes() if processes is None else processes), 'another terminal64 process exists for this user')
    terminal = Path(meta['terminal_dir']) / 'terminal64.exe'
    require(terminal.is_file(), 'terminal executable missing')
    if mode == 'run':
        path = directory / 'stage-verified.json'
        require(path.is_file(), 'genuine stage verification required')
        receipt = json.loads(path.read_text())
        require(receipt['status'] == 'FRESH_SERVER_DEMO20_STAGE_VERIFIED' and
                receipt['nonce'] == meta['nonce'] and receipt['magic'] == meta['magic'] and
                receipt['metadata_hash'] == digest(directory / 'session.json') and
                receipt['hashes'] == meta['hashes'], 'stage receipt binding mismatch')
        identity = receipt['identity']
        require(identity['server'] == 'Exness-MT5Trial7' and identity['account_mode'] == 'ACCOUNT_TRADE_MODE_DEMO' and
                identity['currency'] == 'USD' and identity['margin_mode'] == 'ACCOUNT_MARGIN_MODE_RETAIL_HEDGING' and
                identity['symbol'] == meta.get('symbol', 'XAUUSDm'), 'stage receipt account mismatch')
        require(receipt['audit_key'] == audit_key(identity['server'], identity['login'], meta['magic'], symbol=identity['symbol']), 'stage prefix mismatch')
        marker = directory / 'ACTIVATE_SERVER_DEMO20'
        require(marker.is_file() and marker.read_text().strip() == meta['nonce'], 'explicit session activation marker required')
        persistent = persistent_files(meta, receipt['audit_key'])
        require([file_identity(p) for p in persistent] == receipt['persistent'], 'persistent state replaced')
        validate_hashes(receipt['hashes'])
    convert = windows_path if converter is None else converter
    return ['wine', str(terminal), '/portable', '/config:' + convert(directory / ('RUN.ini' if mode == 'run' else 'STAGE.ini'))]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--session-dir', required=True, type=Path)
    prep.add_argument('--terminal-dir', required=True, type=Path)
    prep.add_argument('--magic', type=int)
    prep.add_argument('--symbol', default='XAUUSDm')
    prep.add_argument('--base-preset', default=None)
    prep.add_argument('--login', default=None)
    verify = commands.add_parser('verify-stage')
    verify.add_argument('--session-dir', required=True, type=Path)
    configure = commands.add_parser('configure-profile')
    configure.add_argument('--session-dir', required=True, type=Path)
    bind = commands.add_parser('bind-preflight')
    bind.add_argument('--session-dir', required=True, type=Path)
    bind.add_argument('--report', required=True, type=Path)
    launch = commands.add_parser('launch')
    launch.add_argument('--session-dir', required=True, type=Path)
    launch.add_argument('--mode', choices=('stage', 'run'), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            prepare(args.session_dir, args.terminal_dir, args.magic, symbol=args.symbol, base_preset=args.base_preset, login=args.login)
            print('FRESH_SERVER_DEMO20_PREPARED')
        elif args.command == 'verify-stage':
            verify_stage(args.session_dir)
            print('FRESH_SERVER_DEMO20_STAGE_VERIFIED')
        elif args.command == 'configure-profile':
            configure_profile(args.session_dir)
            print('FRESH_SERVER_DEMO20_PROFILE_CONFIGURED')
        elif args.command == 'bind-preflight':
            bind_preflight(args.session_dir, args.report)
            print('FRESH_SERVER_DEMO20_CACHED_ACCOUNT_BOUND')
        else:
            arguments = launch_argv(args.session_dir, args.mode)
            prepare_owned_profile(args.session_dir)
            os.execvpe(arguments[0], arguments, os.environ.copy())
    except (GuardError, OSError, ValueError, KeyError, TypeError, configparser.Error, subprocess.SubprocessError):
        # No exceptions containing account data or financial values reach logs.
        parser.exit(1, 'BLOCKED: fresh-server session guard failed; inspect privately, never reset state.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
