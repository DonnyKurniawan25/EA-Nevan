import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PrivateLinkDeliveryTests(unittest.TestCase):
    def load(self):
        path = ROOT / 'tools/send_console_link.py'
        self.assertTrue(path.is_file(), 'private delivery helper not implemented')
        spec = importlib.util.spec_from_file_location('send_console_link', path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_private_button_is_verified_and_receipt_has_no_capability(self):
        module = self.load()
        self.assertEqual(module.ORIGIN, 'https://api.nevstore.id:8443')
        calls = []
        ticket = 'A' * 43
        message = {}
        def api(method, payload):
            calls.append((method, payload))
            if method == 'getChat':
                return {'id': 1227557858, 'type': 'private'}
            if method == 'sendMessage':
                self.assertTrue(payload['protect_content'])
                self.assertNotIn(ticket, payload['text'])
                message.update({'message_id': 9, 'chat': {'id': 1227557858, 'type': 'private'}, 'text': payload['text']})
                return dict(message)
            if method == 'editMessageReplyMarkup':
                message['reply_markup'] = payload['reply_markup']
                return dict(message)
            self.fail('unexpected method')
        result = module.deliver(api, lambda: {'ticket': ticket, 'expires_at': 1900000000})
        self.assertEqual([x[0] for x in calls], ['getChat', 'sendMessage', 'editMessageReplyMarkup'])
        url = message['reply_markup']['inline_keyboard'][0][0]['url']
        self.assertEqual(url, 'https://api.nevstore.id:8443/ea-console/#ticket=' + ticket)
        self.assertEqual(result, {'chat_id': '1227557858', 'message_id': 9, 'expires_at': 1900000000})
        self.assertNotIn(ticket, repr(result))

    def test_main_redacts_provider_errors(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        module = self.load()
        captured = io.StringIO()
        private = 'sensitive-provider-data-DO-NOT-PRINT'
        def failed_api(method, payload):
            raise RuntimeError(private)
        with redirect_stdout(captured), redirect_stderr(captured):
            result = module.main(api=failed_api, issue_ticket=lambda: {})
        self.assertEqual(result, 1)
        self.assertNotIn(private, captured.getvalue())
        self.assertIn('gagal', captured.getvalue())

    def test_rejects_group_destination_before_issuing_any_ticket(self):
        module = self.load()
        calls = []
        def issue():
            calls.append('ticket')
            return {}
        with self.assertRaises(ValueError):
            module.deliver(lambda *args: {'id': -1003987695448, 'type': 'supergroup'}, issue)
        self.assertEqual(calls, [])

if __name__ == '__main__':
    unittest.main()
