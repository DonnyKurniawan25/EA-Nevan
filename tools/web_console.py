#!/usr/bin/env python3
"""Single-use authentication for the private, loopback desktop console."""
import argparse
import asyncio
import json
import os
import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web

PREFIX = "/ea-console/"
COOKIE = "__Secure-goldshield_session"
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self' wss:; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


def create_app(store, *, origin, static_dir, novnc_dir, password_file, vnc_port=5901):
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("an exact HTTPS origin is required")

    @web.middleware
    async def security(request, handler):
        try:
            if request.content_length is not None and request.content_length > 4096:
                raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=request.content_length)
            await asyncio.wait_for(request.read(), 3)
            response = await handler(request)
        except web.HTTPException as exc:
            exc.headers.update(SECURITY_HEADERS)
            raise
        response.headers.update(SECURITY_HEADERS)
        return response

    app = web.Application(client_max_size=4096, middlewares=[security])
    sockets = {}

    async def close_sockets(application):
        await asyncio.gather(*(ws.close(code=1001) for ws in list(sockets.values())), return_exceptions=True)

    app.on_shutdown.append(close_sockets)

    def csrf(request):
        if request.headers.get("Origin") != origin or request.headers.get("X-EA-Console") != "1":
            raise web.HTTPForbidden()

    def authenticated(request):
        session = request.cookies.get(COOKIE)
        expires = store.session_expiry(session)
        if expires is None:
            raise web.HTTPUnauthorized()
        return session, expires

    async def exchange(request):
        csrf(request)
        try:
            body = await request.json()
        except (ValueError, UnicodeError):
            raise web.HTTPBadRequest() from None
        if not isinstance(body, dict) or set(body) != {"ticket"}:
            raise web.HTTPBadRequest()
        result = store.exchange(body["ticket"])
        if result is None:
            raise web.HTTPUnauthorized()
        session, expires = result
        response = web.json_response({"expires_at": expires})
        response.set_cookie(COOKIE, session, path=PREFIX, secure=True, httponly=True,
                            samesite="Strict", max_age=max(0, int(expires - store.clock())))
        return response

    async def current(request):
        _, expires = authenticated(request)
        return web.json_response({"expires_at": expires})

    async def connection(request):
        _, expires = authenticated(request)
        csrf(request)
        try:
            password = Path(password_file).read_text(encoding="utf-8").rstrip("\r\n")
        except (OSError, UnicodeError):
            raise web.HTTPServiceUnavailable() from None
        if not password or len(password) > 256:
            raise web.HTTPServiceUnavailable()
        return web.json_response({"password": password, "expires_at": expires})

    async def logout(request):
        csrf(request)
        session, _ = authenticated(request)
        store.revoke(session)
        response = web.json_response({})
        response.set_cookie(COOKIE, "", path=PREFIX, secure=True, httponly=True,
                            samesite="Strict", max_age=0)
        return response

    def static_file(directory, relative):
        root = Path(directory).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def public_static(request):
        return static_file(static_dir, request.match_info.get("file", "index.html"))

    async def vendor_static(request):
        authenticated(request)
        return static_file(novnc_dir, request.match_info["file"])

    async def websocket(request):
        session, _ = authenticated(request)
        if request.headers.get("Origin") != origin:
            raise web.HTTPForbidden()
        if request.query_string:
            raise web.HTTPBadRequest()
        ws = web.WebSocketResponse(max_msg_size=1024 * 1024, compress=False, timeout=0.5)
        if not ws.can_prepare(request).ok:
            raise web.HTTPBadRequest()
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", vnc_port), 3)
        except (OSError, asyncio.TimeoutError):
            raise web.HTTPServiceUnavailable() from None
        tasks = []
        try:
            ws.headers.update(SECURITY_HEADERS)
            await ws.prepare(request)
            key = token_hash(session)
            previous = sockets.get(key)
            sockets[key] = ws
            if previous is not None:
                await previous.close(code=1008, message=b"connection replaced")

            async def upstream():
                async for message in ws:
                    if message.type == WSMsgType.BINARY:
                        writer.write(message.data)
                        await asyncio.wait_for(writer.drain(), 3)
                    elif message.type == WSMsgType.TEXT:
                        await ws.close(code=1003, message=b"binary required")
                        return

            async def downstream():
                while data := await reader.read(65536):
                    await asyncio.wait_for(ws.send_bytes(data), 3)

            async def watch_session():
                while store.session_expiry(session) is not None:
                    await asyncio.sleep(0.25)
                await ws.close(code=1008, message=b"session ended")

            tasks = [asyncio.create_task(upstream()), asyncio.create_task(downstream()),
                     asyncio.create_task(watch_session())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            if sockets.get(token_hash(session)) is ws:
                sockets.pop(token_hash(session), None)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, asyncio.TimeoutError):
                pass
            await ws.close()
        return ws

    app.router.add_get(PREFIX + "ws", websocket)
    app.router.add_get(PREFIX, public_static)
    app.router.add_get(PREFIX + "{file:app\\.js|app\\.css}", public_static)
    app.router.add_get(PREFIX + "vendor/{file:.+}", vendor_static)
    app.router.add_post(PREFIX + "api/connection", connection)
    app.router.add_post(PREFIX + "api/logout", logout)
    app.router.add_post(PREFIX + "api/session", exchange)
    app.router.add_get(PREFIX + "api/session", current)
    return app

DEFAULT_OWNER = "1227557858"
TICKET_TTL = 900
SESSION_TTL = 1800
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")


def token_hash(token):
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class AuthStore:
    def __init__(self, state_dir, allowed_owner=DEFAULT_OWNER, clock=time.time):
        self.directory = Path(state_dir)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        self.path = self.directory / "auth.sqlite"
        self.allowed_owner = str(allowed_owner)
        self.clock = clock
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS tickets (hash TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
        self.path.chmod(0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def issue_ticket(self, owner_id):
        if str(owner_id) != self.allowed_owner:
            raise PermissionError("owner not allowed")
        token = secrets.token_urlsafe(32)
        expires = int(self.clock()) + TICKET_TTL
        with self.transaction() as db:
            db.execute("DELETE FROM sessions WHERE owner = ?", (self.allowed_owner,))
            db.execute("DELETE FROM tickets WHERE owner = ?", (self.allowed_owner,))
            db.execute("INSERT INTO tickets VALUES (?, ?, ?)", (token_hash(token), self.allowed_owner, expires))
        return {"ticket": token, "expires_at": expires}

    def exchange(self, ticket):
        digest = token_hash(ticket)
        if digest is None:
            return None
        now = self.clock()
        with self.transaction() as db:
            row = db.execute("SELECT expires FROM tickets WHERE hash = ? AND owner = ?", (digest, self.allowed_owner)).fetchone()
            if row is None or row[0] <= now:
                return None
            db.execute("DELETE FROM tickets WHERE hash = ?", (digest,))
            session = secrets.token_urlsafe(32)
            expires = int(now) + SESSION_TTL
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (token_hash(session), self.allowed_owner, expires))
        return session, expires

    def revoke(self, session):
        with self.transaction() as db:
            db.execute("DELETE FROM sessions WHERE hash = ?", (token_hash(session),))

    def session_expiry(self, session):
        digest = token_hash(session)
        if digest is None:
            return None
        with self.transaction() as db:
            row = db.execute("SELECT expires FROM sessions WHERE hash = ? AND owner = ?", (digest, self.allowed_owner)).fetchone()
        return int(row[0]) if row and row[0] > self.clock() else None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private desktop console; never activates trading")
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("issue-ticket")
    issue.add_argument("--state-dir", required=True)
    issue.add_argument("--owner-id", required=True)
    commands.add_parser("serve")
    args = parser.parse_args(argv)
    os.umask(0o077)
    owner = os.environ.get("GOLDSHIELD_CONSOLE_OWNER_ID", DEFAULT_OWNER)
    try:
        if args.command == "issue-ticket":
            if args.owner_id != owner:
                parser.error("owner not allowed")
            store = AuthStore(args.state_dir, allowed_owner=owner)
            print(json.dumps(store.issue_ticket(args.owner_id), separators=(",", ":")))
            return
        store = AuthStore(os.environ.get("GOLDSHIELD_CONSOLE_STATE", "/var/lib/goldshield-console"), allowed_owner=owner)
        app = create_app(store, origin=os.environ["GOLDSHIELD_CONSOLE_ORIGIN"],
                         static_dir=os.environ.get("GOLDSHIELD_CONSOLE_STATIC", "/home/ubuntu/EA-Nevan/deployment/web-console/static"),
                         novnc_dir=os.environ.get("GOLDSHIELD_CONSOLE_NOVNC", "/opt/goldshield-console/noVNC"),
                         password_file=os.environ["GOLDSHIELD_CONSOLE_VNC_PASSWORD_FILE"])
        web.run_app(app, host="127.0.0.1", port=int(os.environ.get("GOLDSHIELD_CONSOLE_PORT", "6091")),
                    access_log=None, print=None, shutdown_timeout=2)
    except (KeyError, ValueError, OSError, sqlite3.Error):
        parser.exit(1, "console configuration or state unavailable\n")


if __name__ == "__main__":
    main()
