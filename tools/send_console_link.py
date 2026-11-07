#!/usr/bin/env python3
"""Deliver an owner-only console link. Never print the link or a credential."""
import re

OWNER_ID = '1227557858'
ORIGIN = 'https://api.nevstore.id:8443'
MESSAGE = (
    '🔒 Akses privat MT5 Server\n\n'
    'Tautan sekali pakai: buka dalam 15 menit. Sesi desktop berlaku 30 menit setelah dibuka. '
    'Jangan teruskan tautan ini.\n\n'
    'Di layar MT5 pilih File → Login to Trade Account, lalu masukkan nomor akun DEMO, '
    'password trading, dan server akun Anda langsung di MT5—bukan di chat. '
    'Biarkan Algo Trading OFF.\n\n'
    'Miringkan HP agar layar lebih luas. Gunakan tombol Keyboard untuk mengetik, '
    'dan Tutup akses setelah selesai. Menutup akses browser tidak mematikan MT5.'
)


def deliver(api, issue_ticket):
    chat = api('getChat', {'chat_id': OWNER_ID})
    if str(chat.get('id')) != OWNER_ID or chat.get('type') != 'private':
        raise ValueError('Private owner destination could not be verified')
    value = issue_ticket()
    token = value.get('ticket', '')
    expiry = value.get('expires_at')
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token) or type(expiry) is not int:
        raise ValueError('Invalid private console ticket')
    url = ORIGIN + '/ea-console/#ticket=' + token
    sent = api('sendMessage', {
        'chat_id': OWNER_ID, 'text': MESSAGE, 'protect_content': True,
        'disable_notification': False, 'link_preview_options': {'is_disabled': True}})
    message_id = sent.get('message_id')
    if str(sent.get('chat', {}).get('id')) != OWNER_ID or type(message_id) is not int or message_id <= 0:
        raise ValueError('Private message acknowledgement invalid')
    markup = {'inline_keyboard': [[{'text': '🔒 Buka MT5 Server', 'url': url}]]}
    observed = api('editMessageReplyMarkup', {
        'chat_id': OWNER_ID, 'message_id': message_id, 'reply_markup': markup})
    if (str(observed.get('chat', {}).get('id')) != OWNER_ID
            or observed.get('message_id') != message_id
            or observed.get('text') != MESSAGE
            or observed.get('reply_markup') != markup):
        raise ValueError('Private console button readback failed')
    return {'chat_id': OWNER_ID, 'message_id': message_id, 'expires_at': expiry}


def main(api=None, issue_ticket=None):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    import urllib.request
    try:
        if api is None:
            path = Path('/etc/goldshield/telegram.env')
            stat = path.stat()
            if os.geteuid() != 0 or stat.st_uid != 0 or stat.st_mode & 0o077 or path.is_symlink():
                raise ValueError('Private root credential file required')
            token = next((line.partition('=')[2].strip().strip('\"\'') for line in path.read_text().splitlines()
                          if line.startswith('TELEGRAM_BOT_TOKEN=')), '')
            if not re.fullmatch(r'[0-9]{5,20}:[A-Za-z0-9_-]{20,100}', token):
                raise ValueError('Bot credential configuration invalid')
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            opener = urllib.request.build_opener(NoRedirect())
            def api(method, payload):
                request = urllib.request.Request(
                    'https://api.telegram.org/bot' + token + '/' + method,
                    data=json.dumps(payload).encode(),
                    headers={'Content-Type': 'application/json'}, method='POST')
                with opener.open(request, timeout=20) as response:
                    value = json.loads(response.read(65537))
                if value.get('ok') is not True or not isinstance(value.get('result'), dict):
                    raise ValueError('Telegram acknowledgement unavailable')
                return value['result']
        if issue_ticket is None:
            def issue_ticket():
                result = subprocess.run([
                    'runuser', '-u', 'goldshield-console', '--',
                    '/opt/goldshield-console/venv/bin/python',
                    str(Path(__file__).with_name('web_console.py')), 'issue-ticket',
                    '--state-dir', '/var/lib/goldshield-console', '--owner-id', OWNER_ID,
                ], capture_output=True, text=True, timeout=20)
                if result.returncode:
                    raise ValueError('Console ticket issuance failed')
                return json.loads(result.stdout)
        receipt = deliver(api, issue_ticket)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except Exception:
        print('Pengiriman akses privat gagal; detail sensitif tidak dicetak.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
