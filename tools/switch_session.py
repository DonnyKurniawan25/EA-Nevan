#!/usr/bin/env python3
"""Session switcher between Weekday Gold (XAUUSDm) and Weekend Crypto (BTCUSDm)."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

WEEKDAY_DIR = Path('/home/ubuntu/goldshield-server-demo/server-20261107')
WEEKEND_DIR = Path('/home/ubuntu/goldshield-server-demo/weekend-btc-20261107')
DROPIN_PATH = Path('/home/ubuntu/.config/systemd/user/goldshield-server-demo.service.d/session.conf')


def get_current_session():
    if not DROPIN_PATH.exists():
        return None
    content = DROPIN_PATH.read_text()
    for line in content.splitlines():
        if line.startswith('Environment=GOLDSHIELD_SESSION_DIR='):
            return Path(line.split('=', 2)[2].strip())
    return None


def switch(target_dir):
    if not target_dir.exists():
        sys.exit(f"Target directory {target_dir} does not exist")
    marker = target_dir / 'ACTIVATE_SERVER_DEMO20'
    if not marker.is_file():
        sys.exit(f"Activation marker missing in {target_dir}")
    receipt = target_dir / 'stage-verified.json'
    if not receipt.is_file():
        sys.exit(f"Stage verification receipt missing in {target_dir}")

    meta = json.loads((target_dir / 'session.json').read_text())
    symbol = meta.get('symbol', 'UNKNOWN')
    magic = meta.get('magic', 0)

    content = f"[Service]\nEnvironment=GOLDSHIELD_SESSION_DIR={target_dir}\nEnvironment=WINEDEBUG=-all\n"
    DROPIN_PATH.write_text(content)

    env = {
        'XDG_RUNTIME_DIR': '/run/user/1000',
        'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus'
    }
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, env=env)
    subprocess.run(['systemctl', '--user', 'restart', 'goldshield-server-demo.service'], check=True, env=env)
    print(f"SWITCHED_TO_{symbol}_MAGIC_{magic}")


def show_status():
    current = get_current_session()
    if current is None:
        print("NO_ACTIVE_SESSION_CONFIGURED")
        return
    meta_path = current / 'session.json'
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        symbol = meta.get('symbol', 'UNKNOWN')
        magic = meta.get('magic', 0)
        print(f"ACTIVE_SESSION: {current.name} (Symbol: {symbol}, Magic: {magic})")
    else:
        print(f"ACTIVE_SESSION_DIR: {current}")


def check_open_positions():
    acc_file = Path("/home/ubuntu/.mt5/drive_c/Program Files/MetaTrader 5/MQL5/Files/GoldShield/account_live.csv")
    if acc_file.exists():
        try:
            lines = acc_file.read_text(errors="ignore").strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split(",")
                return int(parts[4])
        except Exception:
            pass
    return 0


def auto_switch():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    weekday = now.weekday()  # Monday=0, Sunday=6
    hour = now.hour

    is_weekend = False
    if weekday == 4 and hour >= 22:
        is_weekend = True
    elif weekday == 5:
        is_weekend = True
    elif weekday == 6 and hour < 22:
        is_weekend = True

    target_dir = WEEKEND_DIR if is_weekend else WEEKDAY_DIR
    target_name = "weekend (BTCUSDm)" if is_weekend else "weekday (XAUUSDm)"

    current = get_current_session()
    if current and current.resolve() == target_dir.resolve():
        print(f"ALREADY_IN_TARGET_SESSION: {target_name}")
        return 0

    open_pos = check_open_positions()
    if open_pos > 0:
        print(f"CANNOT_SWITCH_OPEN_POSITIONS_ACTIVE: {open_pos} positions open. Waiting for flat state.")
        return 0

    print(f"SWITCHING_SESSION_AUTO: transitioning to {target_name}")
    switch(target_dir)

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tools.telegram_notifier import TelegramSender
        env_file = Path("/etc/goldshield/telegram.env")
        if env_file.exists():
            env_vars = {}
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
            sender = TelegramSender.from_env(env_vars)
            meta = json.loads((target_dir / 'session.json').read_text())
            sym = meta.get('symbol', 'UNKNOWN')
            sender(f"🔄 PERGANTIAN SESI PASAR OTOMATIS\n• Simbol Aktif: {sym}\n• Target: {target_name}\n• Status Posisi: 0 (Aman)\n🛡️ Robot melanjutkan evaluasi trading sesuai jadwal bursa.")
    except Exception as e:
        print(f"Telegram notify error: {e}", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('status')
    sub.add_parser('weekend')
    sub.add_parser('weekday')
    sub.add_parser('auto')
    args = parser.parse_args()

    if args.command == 'weekend':
        switch(WEEKEND_DIR)
    elif args.command == 'weekday':
        switch(WEEKDAY_DIR)
    elif args.command == 'auto':
        auto_switch()
    else:
        show_status()


if __name__ == '__main__':
    main()
