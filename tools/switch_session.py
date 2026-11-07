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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('status')
    sub.add_parser('weekend')
    sub.add_parser('weekday')
    args = parser.parse_args()

    if args.command == 'weekend':
        switch(WEEKEND_DIR)
    elif args.command == 'weekday':
        switch(WEEKDAY_DIR)
    else:
        show_status()


if __name__ == '__main__':
    main()
