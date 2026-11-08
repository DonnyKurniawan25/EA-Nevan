#!/usr/bin/env python3
"""
GoldShield Read-Only Web Monitoring Dashboard
Pure Python stdlib (zero dependencies, zero execution risk).
GET-only endpoints for live trading results, account balance, win-rate, and audit logs.
"""
import csv
import glob
import json
import os
import signal
import subprocess
import sys
import time
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Server configuration
DEFAULT_PORT = 8089
DEFAULT_HOST = "0.0.0.0"
PID_FILE = Path("/tmp/goldshield-dashboard.pid")
DATA_DIR = Path("/home/ubuntu/.mt5/drive_c/Program Files/MetaTrader 5/MQL5/Files/GoldShield")
AUTH_TOKEN = os.environ.get("DASHBOARD_TOKEN", "goldshield-demo")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GoldShield EA — Pemantau Trading</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0b132b;
            --surface: #1c2541;
            --surface-hover: #222e50;
            --card: #141c33;
            --border: #2a375a;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --cyan: #38bdf8;
            --blue: #2563eb;
            --green: #10b981;
            --green-glow: rgba(16, 185, 129, 0.2);
            --red: #ef4444;
            --red-glow: rgba(239, 68, 68, 0.2);
            --amber: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            padding: 16px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 24px;
            margin-bottom: 20px;
        }
        .header-title h1 {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--cyan);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .header-title p {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 4px;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            background: rgba(56, 189, 248, 0.1);
            color: var(--cyan);
            border: 1px solid var(--cyan);
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 8px var(--green);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }
        .grid-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            transition: transform 0.15s ease;
        }
        .card:hover { transform: translateY(-2px); border-color: var(--cyan); }
        .card-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }
        .card-value {
            font-size: 1.6rem;
            font-weight: 700;
            margin: 8px 0;
            font-family: 'JetBrains Mono', monospace;
        }
        .card-sub {
            font-size: 0.8rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .val-green { color: var(--green); }
        .val-red { color: var(--red); }
        .val-cyan { color: var(--cyan); }
        .val-amber { color: var(--amber); }

        .section-box {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .section-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }
        .section-head h2 {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .tab-btn {
            background: var(--card);
            color: var(--text-muted);
            border: 1px solid var(--border);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            margin-left: 6px;
        }
        .tab-btn.active {
            background: var(--blue);
            color: #fff;
            border-color: var(--blue);
        }
        .table-wrap {
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            text-align: left;
        }
        th {
            background: var(--card);
            color: var(--text-muted);
            font-weight: 600;
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }
        td {
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: var(--surface-hover); }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 600;
        }
        .badge-buy { background: rgba(16, 185, 129, 0.15); color: var(--green); border: 1px solid var(--green); }
        .badge-sell { background: rgba(239, 68, 68, 0.15); color: var(--red); border: 1px solid var(--red); }
        .badge-info { background: rgba(56, 189, 248, 0.15); color: var(--cyan); border: 1px solid var(--cyan); }
        .badge-warn { background: rgba(245, 158, 11, 0.15); color: var(--amber); border: 1px solid var(--amber); }

        .auth-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(11, 19, 43, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 999;
        }
        .auth-card {
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 28px;
            border-radius: 12px;
            width: 100%;
            max-width: 360px;
            text-align: center;
        }
        .auth-card input {
            width: 100%;
            padding: 10px 14px;
            background: var(--card);
            border: 1px solid var(--border);
            color: #fff;
            border-radius: 6px;
            margin: 16px 0;
            font-size: 0.9rem;
            outline: none;
        }
        .auth-card button {
            width: 100%;
            padding: 10px;
            background: var(--cyan);
            color: #0b132b;
            font-weight: 700;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }
        .notice-bar {
            background: rgba(56, 189, 248, 0.08);
            border-left: 4px solid var(--cyan);
            padding: 10px 14px;
            border-radius: 4px;
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
    </style>
</head>
<body>
    <div id="authModal" class="auth-overlay" style="display: none;">
        <div class="auth-card">
            <h2 style="font-size: 1.2rem; color: var(--cyan); margin-bottom: 8px;">🔐 Akses Monitor EA</h2>
            <p style="font-size: 0.8rem; color: var(--text-muted);">Masukkan token akses privat untuk membuka dashboard pemantauan.</p>
            <input type="password" id="tokenInput" placeholder="Ketik token di sini...">
            <button onclick="saveToken()">Buka Dashboard</button>
        </div>
    </div>

    <div class="container">
        <header>
            <div class="header-title">
                <h1>🛡️ GoldShield EA <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 400;">v2.0</span></h1>
                <p>Pemantauan Real-Time & Riwayat Trading • Akun Demo Exness (#434492092)</p>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <span class="status-pill" id="eaStatusBadge">
                    <span class="pulse-dot"></span>
                    <span id="eaStatusText">MEMUAT...</span>
                </span>
            </div>
        </header>

        <div class="notice-bar">
            <span>ℹ️</span>
            <span>Dashboard ini bersifat <strong>Murni Pemantauan (Read-Only)</strong>. Tidak ada tombol eksekusi transaksi / pengubah posisi untuk keamanan absolut.</span>
        </div>

        <div class="grid-cards">
            <div class="card">
                <div class="card-label">Saldo Akun (Balance)</div>
                <div class="card-value val-cyan" id="valBalance">$0.00</div>
                <div class="card-sub">Mata Uang: <span id="valCurrency" style="color: #fff; font-weight: 600;">USD</span></div>
            </div>
            <div class="card">
                <div class="card-label">Ekuitas Real-Time (Equity)</div>
                <div class="card-value" id="valEquity">$0.00</div>
                <div class="card-sub">Floating PnL: <span id="valFloating" style="font-weight: 600;">$0.00</span></div>
            </div>
            <div class="card">
                <div class="card-label">Win Rate & Statistik</div>
                <div class="card-value val-green" id="valWinRate">0.0%</div>
                <div class="card-sub">Menang: <strong id="valWins" class="val-green">0</strong> | Kalah: <strong id="valLosses" class="val-red">0</strong></div>
            </div>
            <div class="card">
                <div class="card-label">Total Keuntungan Bersih (PnL)</div>
                <div class="card-value" id="valNetClosed">$0.00</div>
                <div class="card-sub">Kuota Kupon: <span id="valQuota" style="color: #fff;">0 / 20</span> Selesai</div>
            </div>
        </div>

        <!-- Posisi Aktif -->
        <div class="section-box">
            <div class="section-head">
                <h2>📈 Posisi Berjalan di Pasar (<span id="openCount">0</span>)</h2>
                <div style="font-size: 0.8rem; color: var(--text-muted);">Pembaruan otomatis tiap 3 detik</div>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Tiket</th>
                            <th>Simbol</th>
                            <th>Arah</th>
                            <th>Volume</th>
                            <th>Harga Masuk</th>
                            <th>Harga Terkini</th>
                            <th>Stop Loss</th>
                            <th>Take Profit</th>
                            <th>Floating PnL</th>
                        </tr>
                    </thead>
                    <tbody id="openPositionsBody">
                        <tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 16px;">Tidak ada posisi aktif (Akun sedang Flat / Standby)</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Riwayat Transaksi & Audit Sinyal -->
        <div class="section-box">
            <div class="section-head">
                <h2>📋 Catatan Aktivitas & Riwayat</h2>
                <div>
                    <button class="tab-btn active" id="tabDealsBtn" onclick="switchTab('deals')">Riwayat Hasil Transaksi</button>
                    <button class="tab-btn" id="tabAuditBtn" onclick="switchTab('audit')">Log Pengaman & Sinyal</button>
                </div>
            </div>

            <!-- Tab Deals -->
            <div id="dealsView" class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Waktu Server</th>
                            <th>Tiket / Nomor Deal</th>
                            <th>Arah</th>
                            <th>Tipe</th>
                            <th>Volume</th>
                            <th>Harga</th>
                            <th>Hasil Transaksi (Profit)</th>
                            <th>Keterangan</th>
                        </tr>
                    </thead>
                    <tbody id="dealsTableBody">
                        <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 16px;">Memuat riwayat transaksi...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Tab Audit Log -->
            <div id="auditView" class="table-wrap" style="display: none;">
                <table>
                    <thead>
                        <tr>
                            <th>Waktu Server</th>
                            <th>Event Robot</th>
                            <th>Simbol</th>
                            <th>Alasan / Status Pengaman</th>
                            <th>Detail Metrik Pasar</th>
                        </tr>
                    </thead>
                    <tbody id="auditTableBody">
                        <tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">Memuat log pengaman...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let currentTab = 'deals';
        let cachedToken = localStorage.getItem('gs_dashboard_token') || new URLSearchParams(window.location.search).get('token') || '';

        if (cachedToken) {
            localStorage.setItem('gs_dashboard_token', cachedToken);
        }

        function saveToken() {
            const val = document.getElementById('tokenInput').value.trim();
            if (val) {
                localStorage.setItem('gs_dashboard_token', val);
                cachedToken = val;
                document.getElementById('authModal').style.display = 'none';
                fetchData();
            }
        }

        function switchTab(tab) {
            currentTab = tab;
            document.getElementById('tabDealsBtn').className = 'tab-btn' + (tab === 'deals' ? ' active' : '');
            document.getElementById('tabAuditBtn').className = 'tab-btn' + (tab === 'audit' ? ' active' : '');
            document.getElementById('dealsView').style.display = (tab === 'deals' ? 'block' : 'none');
            document.getElementById('auditView').style.display = (tab === 'audit' ? 'block' : 'none');
        }

        async function fetchData() {
            try {
                const res = await fetch('/api/data?token=' + encodeURIComponent(cachedToken));
                if (res.status === 401) {
                    document.getElementById('authModal').style.display = 'flex';
                    return;
                }
                const data = await res.json();
                renderSummary(data.summary);
                renderPositions(data.positions);
                renderDeals(data.deals);
                renderAudit(data.audit);
            } catch (err) {
                console.error("Fetch error:", err);
            }
        }

        function renderSummary(s) {
            if (!s) return;
            document.getElementById('valBalance').innerText = '$' + Number(s.balance || 0).toLocaleString('en-US', {minimumFractionDigits: 2});
            document.getElementById('valCurrency').innerText = s.currency || 'USD';
            
            const eq = Number(s.equity || 0);
            const bal = Number(s.balance || 0);
            const floatPl = eq - bal;
            document.getElementById('valEquity').innerText = '$' + eq.toLocaleString('en-US', {minimumFractionDigits: 2});
            
            const floatEl = document.getElementById('valFloating');
            floatEl.innerText = (floatPl >= 0 ? '+$' : '-$') + Math.abs(floatPl).toFixed(2);
            floatEl.className = floatPl > 0 ? 'val-green' : (floatPl < 0 ? 'val-red' : '');

            const wins = Number(s.wins || 0);
            const losses = Number(s.losses || 0);
            const totalDone = wins + losses;
            const winRate = totalDone > 0 ? ((wins / totalDone) * 100).toFixed(1) : '0.0';
            document.getElementById('valWinRate').innerText = winRate + '%';
            document.getElementById('valWins').innerText = wins;
            document.getElementById('valLosses').innerText = losses;

            const net = Number(s.net_closed || 0);
            const netEl = document.getElementById('valNetClosed');
            netEl.innerText = (net >= 0 ? '+$' : '-$') + Math.abs(net).toFixed(2);
            netEl.className = 'card-value ' + (net >= 0 ? 'val-green' : 'val-red');

            document.getElementById('valQuota').innerText = (s.closed_positions || '0') + ' / ' + (s.limit || '20');

            const stateText = s.core_state || 'READY';
            const reasonText = s.core_reason || '';
            const statusEl = document.getElementById('eaStatusText');
            statusEl.innerText = stateText + (reasonText ? ' (' + reasonText + ')' : '');
        }

        function renderPositions(posList) {
            const tbody = document.getElementById('openPositionsBody');
            document.getElementById('openCount').innerText = posList ? posList.length : 0;
            if (!posList || posList.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 16px;">Tidak ada posisi aktif (Akun sedang Flat / Standby)</td></tr>';
                return;
            }
            tbody.innerHTML = posList.map(p => {
                const pl = Number(p.profit || 0);
                const plClass = pl >= 0 ? 'val-green' : 'val-red';
                const typeBadge = p.type === 'BUY' ? 'badge-buy' : 'badge-sell';
                return `<tr>
                    <td>#${p.ticket}</td>
                    <td><strong>${p.symbol}</strong></td>
                    <td><span class="badge ${typeBadge}">${p.type}</span></td>
                    <td>${p.volume}</td>
                    <td>${p.open_price}</td>
                    <td>${p.current_price}</td>
                    <td>${p.sl || '-'}</td>
                    <td>${p.tp || '-'}</td>
                    <td class="${plClass}" style="font-weight: 700;">${pl >= 0 ? '+' : ''}$${pl.toFixed(2)}</td>
                </tr>`;
            }).join('');
        }

        function renderDeals(deals) {
            const tbody = document.getElementById('dealsTableBody');
            if (!deals || deals.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 16px;">Belum ada catatan riwayat transaksi deal.</td></tr>';
                return;
            }
            tbody.innerHTML = deals.map(d => {
                const pl = Number(d.profit || 0);
                const isExit = (d.entry === 'OUT');
                const plDisplay = isExit ? `<span class="${pl >= 0 ? 'val-green' : 'val-red'}" style="font-weight: 700;">${pl >= 0 ? '+' : ''}$${pl.toFixed(2)}</span>` : '<span style="color: var(--text-muted);">-</span>';
                const typeBadge = d.type === 'BUY' ? 'badge-buy' : 'badge-sell';
                return `<tr>
                    <td>${d.time}</td>
                    <td>#${d.deal}</td>
                    <td><span class="badge ${typeBadge}">${d.type}</span></td>
                    <td><span class="badge ${isExit ? 'badge-warn' : 'badge-info'}">${d.entry}</span></td>
                    <td>${d.volume}</td>
                    <td>${d.price}</td>
                    <td>${plDisplay}</td>
                    <td style="color: var(--text-muted);">${d.comment || '-'}</td>
                </tr>`;
            }).join('');
        }

        function renderAudit(auditList) {
            const tbody = document.getElementById('auditTableBody');
            if (!auditList || auditList.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">Belum ada log pengaman tercatat.</td></tr>';
                return;
            }
            tbody.innerHTML = auditList.slice(0, 35).map(a => {
                let badgeClass = 'badge-info';
                if (a.event === 'STOP_MODIFY' || a.event === 'FRIDAY_PRE_CLOSE') badgeClass = 'badge-warn';
                else if (a.event === 'FILL_CONFIRMED' || a.event === 'TIME_PROFIT_EXIT') badgeClass = 'badge-buy';
                else if (a.event === 'EARLY_REVERSAL_EXIT' || a.event === 'STORAGE_ERROR') badgeClass = 'badge-sell';

                return `<tr>
                    <td>${a.server_time}</td>
                    <td><span class="badge ${badgeClass}">${a.event}</span></td>
                    <td><strong>${a.symbol}</strong></td>
                    <td style="color: var(--cyan);">${a.reason_code}</td>
                    <td style="color: var(--text-muted); font-size: 0.78rem;">${a.details}</td>
                </tr>`;
            }).join('');
        }

        // Init & auto-refresh polling
        fetchData();
        setInterval(fetchData, 3000);
    </script>
</body>
</html>
"""

def parse_csv_file(path):
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return []
        for r in reader:
            if r and len(r) == len(header):
                rows.append(dict(zip(header, r)))
    return rows

def get_latest_data():
    data = {
        "summary": {
            "balance": "0.00",
            "equity": "0.00",
            "currency": "USD",
            "open_positions": "0",
            "limit": "20",
            "closed_positions": "0",
            "wins": "0",
            "losses": "0",
            "net_closed": "0.00",
            "core_state": "READY",
            "core_reason": "STANDBY",
            "trial_status": "RUNNING"
        },
        "positions": [],
        "deals": [],
        "audit": []
    }

    # 1. Parse account_live.csv
    acc_file = DATA_DIR / "account_live.csv"
    acc_rows = parse_csv_file(acc_file)
    if acc_rows:
        latest_acc = acc_rows[-1]
        data["summary"]["balance"] = latest_acc.get("balance", "0.00")
        data["summary"]["equity"] = latest_acc.get("equity", "0.00")
        data["summary"]["currency"] = latest_acc.get("currency", "USD")
        data["summary"]["open_positions"] = latest_acc.get("open_positions", "0")

    # 2. Parse demo20_*.csv (highest mtime)
    demo_files = list(DATA_DIR.glob("demo20_*.csv"))
    if demo_files:
        latest_demo_file = max(demo_files, key=lambda p: p.stat().st_mtime)
        demo_rows = parse_csv_file(latest_demo_file)
        if demo_rows:
            d = demo_rows[-1]
            data["summary"]["limit"] = d.get("limit", "20")
            data["summary"]["closed_positions"] = d.get("closed_positions", "0")
            data["summary"]["wins"] = d.get("wins", "0")
            data["summary"]["losses"] = d.get("losses", "0")
            data["summary"]["net_closed"] = d.get("net_closed", "0.00")
            data["summary"]["core_state"] = d.get("core_state", "READY")
            data["summary"]["core_reason"] = d.get("core_reason", "")
            data["summary"]["trial_status"] = d.get("trial_status", "")

    # 3. Parse positions_live.csv if exists
    pos_file = DATA_DIR / "positions_live.csv"
    data["positions"] = parse_csv_file(pos_file)

    # 4. Parse history_deals.csv if exists
    deal_file = DATA_DIR / "history_deals.csv"
    deals = parse_csv_file(deal_file)
    deals.reverse()
    data["deals"] = deals

    # 5. Parse latest GS2.*.csv for audit logs
    audit_files = list(DATA_DIR.glob("GS2.*.csv"))
    if audit_files:
        latest_audit = max(audit_files, key=lambda p: p.stat().st_mtime)
        audit_rows = parse_csv_file(latest_audit)
        audit_rows.reverse()
        data["audit"] = audit_rows[:50]

    return data


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet logger (no console spam)
        pass

    def check_auth(self):
        query = parse_qs(urlparse(self.path).query)
        token = query.get("token", [""])[0]
        return token == AUTH_TOKEN

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        elif parsed.path == "/api/data":
            if not self.check_auth():
                self.send_response(HTTPStatus.UNAUTHORIZED)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            payload = get_latest_data()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        elif parsed.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()


def run_server(port=DEFAULT_PORT, host=DEFAULT_HOST):
    server = HTTPServer((host, port), DashboardHandler)
    PID_FILE.write_text(str(os.getpid()))
    print(f"GoldShield Dashboard running on http://{host}:{port} (PID {os.getpid()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


def cmd_start():
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"Dashboard ALREADY RUNNING (PID {pid}). Port: {DEFAULT_PORT}")
            return
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    # Spawn daemon process
    cmd = [sys.executable, str(Path(__file__).resolve()), "serve"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)
    time.sleep(1)
    if proc.poll() is None:
        print(f"SUCCESS: Dashboard AKTIF pada port {DEFAULT_PORT} (PID {proc.pid})")
        print(f"Akses URL: http://103.42.245.236:{DEFAULT_PORT}/?token={AUTH_TOKEN}")
    else:
        print("ERROR: Gagal menyalakan dashboard.")


def cmd_stop():
    if not PID_FILE.exists():
        print("Dashboard SUDAH MATI (Tidak ada proses aktif).")
        return
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        PID_FILE.unlink(missing_ok=True)
        print(f"SUCCESS: Dashboard (PID {pid}) berhasil DIMATIKAN.")
    except Exception as e:
        print(f"Error stopping dashboard: {e}")
        PID_FILE.unlink(missing_ok=True)


def cmd_status():
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"STATUS: AKTIF (PID {pid})")
            print(f"Akses URL: http://103.42.245.236:{DEFAULT_PORT}/?token={AUTH_TOKEN}")
            return
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    print("STATUS: NON-AKTIF (Mati)")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "serve":
        run_server()
    elif action == "start":
        cmd_start()
    elif action == "stop":
        cmd_stop()
    elif action == "status":
        cmd_status()
    else:
        print(f"Usage: {sys.argv[0]} {{start|stop|status}}")
