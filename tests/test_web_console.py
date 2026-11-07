"""Loopback-only console tests: no broker, real secrets, or service access."""
import asyncio
from aiohttp import ClientSession, DummyCookieJar, WSMsgType, WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import sqlite3
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "web_console.py"
spec = importlib.util.spec_from_file_location("web_console", SOURCE)
console = importlib.util.module_from_spec(spec) if SOURCE.exists() else None
if console:
    spec.loader.exec_module(console)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = [1000.0]

    def test_single_use_hash_only_and_absolute_expiry(self):
        self.assertIsNotNone(console, "console backend is missing")
        store = console.AuthStore(self.temp.name, clock=lambda: self.now[0])
        issued = store.issue_ticket("1227557858")
        self.assertEqual(set(issued), {"ticket", "expires_at"})
        self.assertEqual(issued["expires_at"], 1900)
        session, expiry = store.exchange(issued["ticket"])
        self.assertEqual(expiry, 2800)
        self.assertIsNone(store.exchange(issued["ticket"]))
        self.assertEqual(store.session_expiry(session), 2800)
        with sqlite3.connect(Path(self.temp.name) / "auth.sqlite") as db:
            contents = repr(db.execute("SELECT * FROM sessions").fetchall())
        self.assertNotIn(issued["ticket"], contents)
        self.assertNotIn(session, contents)
        self.now[0] = 2800
        self.assertIsNone(store.session_expiry(session))

    def test_cli_emits_only_json_and_denies_other_owner(self):
        command = [sys.executable, str(SOURCE), "issue-ticket", "--state-dir", self.temp.name, "--owner-id"]
        result = subprocess.run(command + ["1227557858"], capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, "")
        issued = json.loads(result.stdout)
        self.assertEqual(set(issued), {"ticket", "expires_at"})
        self.assertEqual(len(issued["ticket"]), 43)
        rejected = subprocess.run(command + ["999"], capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, "")
        self.assertNotIn(issued["ticket"], rejected.stderr)

    def test_issue_revokes_previous_owner_material_and_rejects_expired(self):
        store = console.AuthStore(self.temp.name, clock=lambda: self.now[0])
        first = store.issue_ticket("1227557858")
        session, _ = store.exchange(first["ticket"])
        second = store.issue_ticket("1227557858")
        self.assertIsNone(store.session_expiry(session))
        self.now[0] = second["expires_at"]
        self.assertIsNone(store.exchange(second["ticket"]))
        with self.assertRaises(PermissionError):
            store.issue_ticket("999")
        third = store.issue_ticket("1227557858")
        fourth = store.issue_ticket("1227557858")
        self.assertIsNone(store.exchange(third["ticket"]))
        session, _ = store.exchange(fourth["ticket"])
        store.revoke(session)
        self.assertIsNone(store.session_expiry(session))


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = [1000.0]
        self.store = console.AuthStore(self.root / "state", clock=lambda: self.now[0])
        self.origin = "https://api.nevstore.id:8443"
        self.headers = {"Origin": self.origin, "X-EA-Console": "1"}
        self.secret = self.root / "vnc-password"
        self.secret.write_text("fake-vnc-only\n")
        self.static = self.root / "static"
        self.vendor = self.root / "vendor"
        self.static.mkdir()
        self.vendor.mkdir()
        for filename in ("index.html", "app.js", "app.css"):
            (self.static / filename).write_text("fixture")
        (self.vendor / "rfb.js").write_text("fixture module")
        self.tcp_bytes = bytearray()
        async def echo(reader, writer):
            try:
                while data := await reader.read(65536):
                    self.tcp_bytes.extend(data)
                    writer.write(data)
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        self.echo = await asyncio.start_server(echo, "127.0.0.1", 0)
        async def stop_echo():
            self.echo.close()
            await self.echo.wait_closed()
        self.addAsyncCleanup(stop_echo)
        self.app = console.create_app(self.store, origin=self.origin, static_dir=self.static,
                                      novnc_dir=self.vendor, password_file=self.secret,
                                      vnc_port=self.echo.sockets[0].getsockname()[1])
        self.client = TestClient(TestServer(self.app), cookie_jar=DummyCookieJar())
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def login(self):
        ticket = self.store.issue_ticket("1227557858")["ticket"]
        response = await self.client.post("/ea-console/api/session", json={"ticket": ticket}, headers=self.headers)
        self.assertEqual(response.status, 200)
        return {**self.headers, "Cookie": "__Secure-goldshield_session=" + response.cookies["__Secure-goldshield_session"].value}

    async def test_connection_uses_post_so_browser_supplies_origin(self):
        headers = await self.login()
        response = await self.client.post("/ea-console/api/connection", headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["password"], "fake-vnc-only")
        self.assertEqual((await self.client.get("/ea-console/api/connection", headers=headers)).status, 405)

    async def test_connection_secret_needs_header_and_logout_revokes(self):
        headers = await self.login()
        url = "/ea-console/api/connection"
        self.assertEqual((await self.client.post(url)).status, 401)
        self.assertEqual((await self.client.post(url, headers={"Cookie": headers["Cookie"]})).status, 403)
        response = await self.client.post(url, headers=headers)
        self.assertEqual(await response.json(), {"password": "fake-vnc-only", "expires_at": 2800})
        self.assertEqual((await self.client.post("/ea-console/api/logout", headers={"Cookie": headers["Cookie"]})).status, 403)
        response = await self.client.post("/ea-console/api/logout", headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.cookies["__Secure-goldshield_session"]["max-age"], "0")
        self.assertEqual((await self.client.post(url, headers=headers)).status, 401)

    async def test_static_vendor_authorization_traversal_and_security_headers(self):
        for suffix in ("", "app.js", "app.css"):
            response = await self.client.get("/ea-console/" + suffix)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual((await self.client.get("/ea-console/vendor/rfb.js")).status, 401)
        headers = await self.login()
        self.assertEqual((await self.client.get("/ea-console/vendor/rfb.js", headers=headers)).status, 200)
        (self.vendor / "outside.js").symlink_to(self.secret)
        for suffix in ("outside.js", "%2e%2e/vnc-password", "%2e%2e%2fvnc-password"):
            self.assertNotEqual((await self.client.get("/ea-console/vendor/" + suffix, headers=headers)).status, 200)
        self.assertEqual((await self.client.get("/ea-console/unknown")).status, 404)

    async def test_binary_ws_real_loopback_echo_and_text_rejection(self):
        headers = await self.login()
        async with self.client.ws_connect("/ea-console/ws", headers=headers) as ws:
            await ws.send_bytes(b"\x00\xffRFB fixture")
            message = await asyncio.wait_for(ws.receive(), 1)
            self.assertEqual(message.type, WSMsgType.BINARY)
            self.assertEqual(message.data, b"\x00\xffRFB fixture")
            self.assertEqual(ws._response.headers["Cache-Control"], "no-store")
            await ws.send_str("not VNC")
            message = await asyncio.wait_for(ws.receive(), 1)
            self.assertEqual(message.type, WSMsgType.CLOSE)
            self.assertEqual(message.data, 1003)
        self.assertEqual(self.tcp_bytes, b"\x00\xffRFB fixture")

    async def test_live_ws_closes_on_expiry_reissue_and_logout(self):
        for action in ("expiry", "reissue", "logout"):
            headers = await self.login()
            ws = await self.client.ws_connect("/ea-console/ws", headers=headers)
            if action == "expiry":
                self.now[0] += 1800
            elif action == "reissue":
                self.store.issue_ticket("1227557858")
            else:
                response = await self.client.post("/ea-console/api/logout", headers=headers)
                self.assertEqual(response.status, 200)
            try:
                message = await asyncio.wait_for(ws.receive(), 1.8)
                self.assertEqual(message.type, WSMsgType.CLOSE)
            finally:
                await ws.close()

    async def test_second_ws_replaces_first_and_denies_untrusted_handshake(self):
        headers = await self.login()
        for bad_headers, suffix, status in (({}, "", 401), ({**headers, "Origin": "https://evil.example"}, "", 403),
                                             (headers, "?host=elsewhere&port=22", 400)):
            with self.assertRaises(WSServerHandshakeError) as raised:
                await self.client.ws_connect("/ea-console/ws" + suffix, headers=bad_headers)
            self.assertEqual(raised.exception.status, status)
        first = await self.client.ws_connect("/ea-console/ws", headers=headers)
        second = await self.client.ws_connect("/ea-console/ws", headers=headers)
        try:
            self.assertEqual((await asyncio.wait_for(first.receive(), 1.8)).type, WSMsgType.CLOSE)
            await second.send_bytes(b"second")
            self.assertEqual((await asyncio.wait_for(second.receive(), 1)).data, b"second")
        finally:
            await first.close()
            await second.close()

    async def test_body_limit_chunked_and_ws_frame_bound(self):
        async def oversized():
            yield b"x" * 4097
        response = await self.client.get("/ea-console/", data=oversized())
        self.assertEqual(response.status, 413)
        headers = await self.login()
        async with self.client.ws_connect("/ea-console/ws", headers=headers) as ws:
            await ws.send_bytes(b"x" * (1024 * 1024 + 1))
            self.assertEqual((await asyncio.wait_for(ws.receive(), 1.8)).type, WSMsgType.CLOSE)
        self.assertEqual(self.tcp_bytes, b"")

    async def test_exchange_cookie_origin_and_no_store(self):
        ticket = self.store.issue_ticket("1227557858")["ticket"]
        url = "/ea-console/api/session"
        self.assertEqual((await self.client.get(url)).status, 401)
        self.assertEqual((await self.client.post(url, json={"ticket": ticket})).status, 403)
        response = await self.client.post(url, json={"ticket": ticket}, headers=self.headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"expires_at": 2800})
        cookie = response.cookies["__Secure-goldshield_session"]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/ea-console/")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual((await self.client.post(url, json={"ticket": ticket}, headers=self.headers)).status, 401)
        headers = {"Cookie": "__Secure-goldshield_session=" + cookie.value}
        self.assertEqual(await (await self.client.get(url, headers=headers)).json(), {"expires_at": 2800})
        self.now[0] = 2800
        self.assertEqual((await self.client.get(url, headers=headers)).status, 401)


if __name__ == "__main__":
    unittest.main()
