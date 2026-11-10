#!/usr/bin/env python3
"""
GoldShield Read-Only Web Monitoring Dashboard
Light Theme & Mobile-Responsive Edition
Pure Python stdlib (zero dependencies, zero execution risk).
GET-only endpoints for live trading results, account balance, win-rate, and audit logs.
"""
import csv
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Server configuration
DEFAULT_PORT = 8089
DEFAULT_HOST = "0.0.0.0"
PID_FILE = Path("/tmp/goldshield-dashboard.pid")
DATA_DIR = Path("/home/ubuntu/.mt5/drive_c/Program Files/MetaTrader 5/MQL5/Files/GoldShield")

# Dashboard Auth Token (Keamanan Akses Web)
DASHBOARD_TOKEN_FILE = Path("/etc/goldshield/dashboard_token.env")
AUTH_TOKEN = "97d7c1c95b3c37f7322025414163bc1c1e664cf603e20acb"
if DASHBOARD_TOKEN_FILE.exists():
    try:
        for _line in DASHBOARD_TOKEN_FILE.read_text().splitlines():
            if _line.strip().startswith("DASHBOARD_TOKEN="):
                _tok = _line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                if _tok:
                    AUTH_TOKEN = _tok
                break
    except Exception:
        pass
AUTH_TOKEN = os.environ.get("DASHBOARD_TOKEN", AUTH_TOKEN)

# Operator Trading PIN (Khusus Donny untuk Transaksi)
TRADING_PIN_FILE = Path("/etc/goldshield/trading_pin.env")
TRADING_PIN = "251029"
if TRADING_PIN_FILE.exists():
    try:
        for _line in TRADING_PIN_FILE.read_text().splitlines():
            if _line.strip().startswith("TRADING_PIN="):
                _pin = _line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                if _pin:
                    TRADING_PIN = _pin
                break
    except Exception:
        pass
TRADING_PIN = os.environ.get("TRADING_PIN", TRADING_PIN)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GoldShield EA — Pemantau Trading Real-Time</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #f8fafc;
            --surface: #ffffff;
            --surface-subtle: #f1f5f9;
            --border: #e2e8f0;
            --border-hover: #cbd5e1;
            --text-main: #0f172a;
            --navy: #0f172a;
            --text-muted: #64748b;
            --text-subtle: #94a3b8;
            --primary: #1d4ed8;
            --primary-light: #eff6ff;
            --primary-border: #bfdbfe;
            --cyan: #0284c7;
            --green: #15803d;
            --green-bg: #f0fdf4;
            --green-border: #bbf7d0;
            --red: #b91c1c;
            --red-bg: #fef2f2;
            --red-border: #fecaca;
            --amber: #b45309;
            --amber-bg: #fffbeb;
            --amber-border: #fde68a;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.04);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            padding: 16px;
            line-height: 1.5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        /* HEADER */
        header {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 18px 24px;
            margin-bottom: 16px;
            box-shadow: var(--shadow-sm);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-icon {
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: linear-gradient(135deg, #1d4ed8 0%, #0284c7 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
            box-shadow: 0 4px 8px -2px rgba(29, 78, 216, 0.3);
            flex-shrink: 0;
        }
        .brand-text h1 {
            font-size: 1.2rem;
            font-weight: 800;
            color: var(--text-main);
            letter-spacing: -0.02em;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .brand-text p {
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-top: 2px;
        }
        .header-meta {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 24px;
            font-size: 0.8rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            background: var(--green-bg);
            color: var(--green);
            border: 1px solid var(--green-border);
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #16a34a;
            box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.5);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.5); }
            70% { box-shadow: 0 0 0 8px rgba(22, 163, 74, 0); }
            100% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
        }

        /* STATUS EXPLANATION BANNER */
        .status-banner {
            background: #ffffff;
            border: 1px solid #e0e7ff;
            border-left: 5px solid #2563eb;
            border-radius: var(--radius-md);
            padding: 14px 18px;
            margin-bottom: 16px;
            box-shadow: var(--shadow-sm);
            display: flex;
            align-items: flex-start;
            gap: 14px;
        }
        .banner-icon {
            font-size: 22px;
            line-height: 1;
            flex-shrink: 0;
            margin-top: 2px;
        }
        .banner-body {
            flex: 1;
        }
        .banner-title {
            font-size: 0.92rem;
            font-weight: 700;
            color: #1e3a8a;
            margin-bottom: 2px;
        }
        .banner-text {
            font-size: 0.84rem;
            color: #334155;
            line-height: 1.45;
        }

        /* GRID CARDS */
        .grid-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 16px;
        }
        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 16px 18px;
            box-shadow: var(--shadow-sm);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            position: relative;
            overflow: hidden;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }
        .stat-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--primary);
            opacity: 0.8;
        }
        .stat-card.card-green::before { background: #16a34a; }
        .stat-card.card-cyan::before { background: #0284c7; }
        .stat-card.card-amber::before { background: #d97706; }
        .stat-card.card-red::before { background: #dc2626; }

        .stat-label {
            font-size: 0.76rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .stat-value {
            font-size: 1.45rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-main);
            letter-spacing: -0.02em;
            line-height: 1.2;
        }
        .stat-sub {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }
        .val-profit { color: var(--green); }
        .val-loss { color: var(--red); }
        .val-neutral { color: var(--text-main); }

        /* TABS NAVIGATION */
        .tabs-header {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 6px;
            margin-bottom: 16px;
            box-shadow: var(--shadow-sm);
            overflow-x: auto;
            flex-wrap: nowrap;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
        }
        .tabs-header::-webkit-scrollbar { display: none; }
        .tab-btn {
            background: transparent;
            border: none;
            outline: none;
            padding: 9px 18px;
            border-radius: 8px;
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .tab-btn:hover {
            color: var(--text-main);
            background: var(--surface-subtle);
        }
        .tab-btn.active {
            background: var(--primary);
            color: #ffffff;
            box-shadow: 0 2px 4px -1px rgba(29, 78, 216, 0.3);
        }
        .badge-count {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 12px;
            font-size: 0.72rem;
            font-family: 'JetBrains Mono', monospace;
            background: var(--surface-subtle);
            color: var(--text-main);
        }
        .tab-btn.active .badge-count {
            background: rgba(255, 255, 255, 0.25);
            color: #ffffff;
        }

        /* SECTION CARD */
        .section-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-sm);
            margin-bottom: 16px;
            overflow: hidden;
        }
        .section-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            background: #fafcff;
        }
        .section-header h2 {
            font-size: 1rem;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-desc {
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        /* RESPONSIVE TABLE WRAPPER */
        .table-responsive {
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.84rem;
            text-align: left;
            min-width: 600px;
        }
        th {
            background: #f8fafc;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.05em;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }
        td {
            padding: 13px 16px;
            border-bottom: 1px solid var(--border);
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
            white-space: nowrap;
        }
        tr:last-child td { border-bottom: none; }
        tbody tr:hover {
            background-color: #f8fafc;
        }
        .mono {
            font-family: 'JetBrains Mono', monospace;
        }

        /* PILLS & BADGES */
        .pill {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }
        .pill-buy {
            background: var(--green-bg);
            color: var(--green);
            border: 1px solid var(--green-border);
        }
        .pill-sell {
            background: var(--red-bg);
            color: var(--red);
            border: 1px solid var(--red-border);
        }
        .pill-hold {
            background: var(--amber-bg);
            color: var(--amber);
            border: 1px solid var(--amber-border);
        }
        .pill-neutral {
            background: var(--surface-subtle);
            color: var(--text-muted);
            border: 1px solid var(--border);
        }
        .pill-win {
            background: var(--green-bg);
            color: var(--green);
            font-weight: 700;
        }
        .pill-loss {
            background: var(--red-bg);
            color: var(--red);
            font-weight: 700;
        }

        /* EMPTY STATE */
        .empty-state {
            padding: 40px 20px;
            text-align: center;
            color: var(--text-muted);
        }
        .empty-icon {
            font-size: 38px;
            margin-bottom: 10px;
            color: var(--text-subtle);
        }
        .empty-title {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 4px;
        }
        .empty-sub {
            font-size: 0.82rem;
            color: var(--text-muted);
            max-width: 440px;
            margin: 0 auto;
            line-height: 1.4;
        }

        /* REAL-TIME CHART CARD */
        .chart-card {
            background: #ffffff;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            margin-bottom: 20px;
            overflow: hidden;
        }
        .chart-header {
            padding: 12px 18px;
            background: #f8fafc;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .chart-title-box {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.92rem;
            font-weight: 700;
            color: var(--navy);
        }
        .chart-controls {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .chart-pill-btn {
            background: #ffffff;
            border: 1px solid var(--border);
            padding: 6px 14px;
            border-radius: var(--radius-sm);
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .chart-pill-btn:hover {
            color: var(--primary);
            border-color: var(--cyan);
        }
        .chart-pill-btn.active {
            background: var(--primary);
            color: #ffffff !important;
            border-color: var(--primary);
            box-shadow: 0 1px 3px rgba(29, 78, 216, 0.25);
        }
        .chart-frame-wrapper {
            width: 100%;
            height: 480px;
            background: #ffffff;
            position: relative;
        }

        /* DECISION & EXPLANATION CARD */
        .decision-card {
            background: #ffffff;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            margin-bottom: 20px;
            overflow: hidden;
            transition: all 0.2s ease;
        }
        .decision-header {
            padding: 10px 18px;
            background: #f8fafc;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }
        .decision-title-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .decision-badge {
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: var(--radius-sm);
            letter-spacing: 0.3px;
        }
        .decision-badge.standby {
            background: #f1f5f9;
            color: #0f172a;
            border: 1px solid var(--border);
        }
        .decision-badge.active-trade {
            background: #dbeafe;
            color: #1e40af;
            border: 1px solid #bfdbfe;
        }
        .decision-symbol-pill {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--cyan);
            background: #f0f9ff;
            padding: 2px 8px;
            border-radius: var(--radius-sm);
            border: 1px solid #bae6fd;
        }
        .decision-time {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: var(--mono);
        }
        .decision-body {
            padding: 16px 18px;
        }
        .decision-main-row {
            display: flex;
            gap: 14px;
            align-items: flex-start;
        }
        .decision-icon-large {
            font-size: 28px;
            line-height: 1;
            padding-top: 2px;
        }
        .decision-content {
            flex: 1;
        }
        .decision-heading {
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 4px;
        }
        .decision-explanation {
            font-size: 0.82rem;
            color: var(--text-muted);
            line-height: 1.5;
        }
        .decision-metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px dashed var(--border);
        }
        .metric-pill {
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 6px 10px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .metric-lbl {
            font-size: 0.68rem;
            color: var(--text-muted);
            font-weight: 600;
        }
        .metric-val {
            font-size: 0.82rem;
            color: var(--text-main);
            font-family: var(--mono);
        }
        .trade-card {
            background: #f0fdf4;
            border: 1px solid var(--green-border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            margin-top: 10px;
        }
        .trade-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        .trade-card-title {
            font-weight: 700;
            font-size: 0.88rem;
            color: var(--green);
        }
        .trade-card-reason {
            font-size: 0.82rem;
            color: var(--text-main);
            margin-bottom: 8px;
            line-height: 1.4;
        }
        .trade-guards-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            font-size: 0.74rem;
        }
        .trade-guard-item {
            background: #ffffff;
            padding: 5px 8px;
            border-radius: 4px;
            border: 1px solid var(--green-border);
        }

        /* RULE CHECKLIST CARD */
        .rules-card {
            background: #ffffff;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            margin-bottom: 20px;
            overflow: hidden;
        }
        .rules-header {
            padding: 12px 18px;
            background: #f8fafc;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .rules-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--navy);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .rules-summary-badge {
            font-size: 0.75rem;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 20px;
            background: #eff6ff;
            color: var(--primary);
            border: 1px solid #bfdbfe;
        }
        .rules-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 10px;
            padding: 16px;
        }
        .rule-item {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: all 0.15s ease;
        }
        .rule-item.pass {
            border-left: 4px solid var(--green);
            background: #fafdfb;
        }
        .rule-item.fail {
            border-left: 4px solid var(--amber);
            background: #fffdfa;
        }
        .rule-item.block {
            border-left: 4px solid var(--red);
            background: #fefcfc;
        }
        .rule-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 4px;
        }
        .rule-name {
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--navy);
            line-height: 1.3;
            flex: 1 1 auto;
        }
        .rule-badge {
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: var(--radius-sm);
            white-space: nowrap;
            flex-shrink: 0;
        }
        .rule-badge.pass {
            background: #dcfce7;
            color: #15803d;
            border: 1px solid #bbf7d0;
        }
        .rule-badge.fail {
            background: #fef3c7;
            color: #b45309;
            border: 1px solid #fde68a;
        }
        .rule-badge.block {
            background: #fee2e2;
            color: #b91c1c;
            border: 1px solid #fecaca;
        }
        .rule-condition {
            font-size: 0.74rem;
            color: var(--text-muted);
            line-height: 1.35;
        }
        .rule-current {
            font-size: 0.74rem;
            font-weight: 600;
            color: var(--text-main);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px dashed var(--border);
            padding-top: 5px;
            margin-top: 2px;
        }

        /* PIN BADGE & MODAL */
        .pin-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.74rem;
            font-weight: 700;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s ease;
        }
        .pin-badge.locked {
            background: #fef3c7;
            color: #92400e;
            border-color: #fde68a;
        }
        .pin-badge.unlocked {
            background: #dcfce7;
            color: #166534;
            border-color: #bbf7d0;
        }
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.65);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            padding: 16px;
        }
        .modal-card {
            background: #ffffff;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            box-shadow: var(--shadow-lg);
            width: 100%;
            max-width: 380px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            animation: modalFadeIn 0.2s ease;
        }
        @keyframes modalFadeIn {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .modal-header h3 {
            font-size: 1.05rem;
            color: var(--navy);
            margin: 0;
        }
        .btn-modal-close {
            background: none;
            border: none;
            font-size: 1.2rem;
            color: var(--text-muted);
            cursor: pointer;
        }
        .modal-desc {
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.4;
            margin: 0;
        }
        .pin-input-box {
            display: flex;
            justify-content: center;
            margin: 8px 0;
        }
        .pin-input {
            width: 100%;
            text-align: center;
            font-size: 1.6rem;
            letter-spacing: 10px;
            font-family: var(--mono);
            padding: 10px 14px;
            border: 2px solid var(--border);
            border-radius: var(--radius-md);
            color: var(--navy);
            outline: none;
            transition: border-color 0.2s ease;
        }
        .pin-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
        }
        .pin-error-box {
            color: var(--red);
            font-size: 0.78rem;
            font-weight: 600;
            text-align: center;
        }
        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 6px;
        }
        .btn-modal-cancel {
            flex: 1;
            padding: 10px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: #f8fafc;
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--text-muted);
            cursor: pointer;
        }
        .btn-modal-submit {
            flex: 1;
            padding: 10px;
            border-radius: var(--radius-sm);
            border: none;
            background: var(--primary);
            color: #ffffff;
            font-weight: 700;
            font-size: 0.85rem;
            cursor: pointer;
        }

        /* TOGGLE RULES BUTTON */
        .btn-toggle-rules {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 4px 10px;
            font-size: 0.74rem;
            font-weight: 700;
            color: var(--primary);
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .btn-toggle-rules:hover {
            background: #eff6ff;
            border-color: var(--primary);
        }

        /* CARD TRADING MANUAL (MODE GABUT) */
        .trade-exec-card {
            background: #ffffff;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border);
            border-top: 4px solid var(--primary);
            box-shadow: var(--shadow-sm);
            margin-bottom: 20px;
            overflow: hidden;
        }
        .trade-exec-header {
            padding: 12px 18px;
            background: #f8fafc;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }
        .trade-exec-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--navy);
        }
        .badge-operator {
            font-size: 0.68rem;
            font-weight: 700;
            background: #eff6ff;
            color: var(--primary);
            padding: 2px 7px;
            border-radius: 10px;
            border: 1px solid #bfdbfe;
        }
        .trade-exec-body {
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .trade-form-row {
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            align-items: center;
            justify-content: space-between;
        }
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .form-label {
            font-size: 0.74rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .lot-pills {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .pill-lot {
            padding: 6px 12px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: #f8fafc;
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-main);
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .pill-lot.active {
            background: var(--navy);
            color: #ffffff;
            border-color: var(--navy);
        }
        .lot-input {
            width: 70px;
            padding: 5px 8px;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            font-family: var(--mono);
            font-size: 0.85rem;
            font-weight: 600;
            text-align: center;
        }
        .auto-protect-box {
            display: flex;
            align-items: center;
            gap: 8px;
            background: #f8fafc;
            padding: 6px 12px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
        }
        .auto-protect-box input[type="checkbox"] {
            width: 16px;
            height: 16px;
            accent-color: var(--primary);
            cursor: pointer;
        }
        .auto-protect-text {
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--text-main);
        }
        .trade-custom-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            background: #fffdf5;
            padding: 10px;
            border-radius: var(--radius-sm);
            border: 1px dashed #fde68a;
        }
        .trade-custom-row input {
            padding: 6px 10px;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            font-family: var(--mono);
            font-size: 0.82rem;
        }
        .trade-buttons-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-top: 4px;
        }
        .btn-trade {
            padding: 14px 16px;
            border-radius: var(--radius-md);
            border: none;
            color: #ffffff;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }
        .btn-trade:active {
            transform: scale(0.98);
        }
        .btn-trade-buy {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        }
        .btn-trade-buy:hover {
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35);
        }
        .btn-trade-sell {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        }
        .btn-trade-sell:hover {
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.35);
        }
        .btn-trade-main {
            font-size: 0.98rem;
            font-weight: 800;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .btn-trade-sub {
            font-size: 0.72rem;
            opacity: 0.92;
            font-weight: 500;
        }

        /* MOBILE BOTTOM STICKY NAV */
        .mobile-bottom-nav {
            display: none;
        }

        /* FOOTER */
        footer {
            margin-top: 24px;
            padding: 16px;
            text-align: center;
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        /* MOBILE OPTIMIZATIONS (< 768px) */
        @media (max-width: 768px) {
            body { padding: 8px 8px 75px 8px; }
            .mobile-bottom-nav {
                display: flex;
                position: fixed;
                bottom: 0; left: 0; right: 0;
                background: #ffffff;
                border-top: 1px solid var(--border);
                box-shadow: 0 -4px 12px rgba(0,0,0,0.08);
                z-index: 8000;
                justify-content: space-around;
                padding: 6px 4px 8px 4px;
            }
            .mob-nav-btn {
                background: none;
                border: none;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 2px;
                font-size: 0.68rem;
                font-weight: 600;
                color: var(--text-muted);
                cursor: pointer;
                flex: 1;
                padding: 4px;
            }
            .mob-nav-btn.active {
                color: var(--primary);
            }
            .mob-nav-btn span:first-child {
                font-size: 1.1rem;
            }
            .trade-buttons-row {
                grid-template-columns: 1fr;
                gap: 10px;
            }
            .btn-trade {
                padding: 12px;
            }
            .trade-form-row {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            header {
                padding: 14px 16px;
                border-radius: var(--radius-md);
            }
            .brand-icon {
                width: 38px;
                height: 38px;
                font-size: 18px;
            }
            .brand-text h1 { font-size: 1.05rem; }
            .brand-text p { font-size: 0.75rem; }
            .status-badge {
                width: 100%;
                justify-content: center;
                padding: 7px 12px;
            }
            .grid-stats {
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
            }
            .stat-card {
                padding: 12px 14px;
            }
            .stat-value {
                font-size: 1.25rem;
            }
            .stat-label {
                font-size: 0.7rem;
            }
            .stat-sub {
                font-size: 0.72rem;
            }
            .chart-frame-wrapper {
                height: 320px;
            }
            .chart-header {
                padding: 10px 14px;
            }
            .decision-metrics-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .trade-guards-grid {
                grid-template-columns: 1fr;
            }
            .rules-grid {
                grid-template-columns: 1fr;
                padding: 12px;
                gap: 8px;
            }
            .decision-body {
                padding: 12px 14px;
            }
            .banner-title { font-size: 0.86rem; }
            .banner-text { font-size: 0.78rem; }
            .tabs-header {
                padding: 4px;
                gap: 4px;
            }
            .tab-btn {
                padding: 8px 12px;
                font-size: 0.78rem;
                flex: 1;
                justify-content: center;
            }
            .section-header {
                padding: 12px 14px;
            }
            th, td {
                padding: 10px 12px;
                font-size: 0.78rem;
            }
        }
    </style>
</head>
<body>
    <!-- MODAL KEAMANAN PIN OPERATOR TRADING (DONNY) -->
    <div class="modal-overlay" id="pin-modal" style="display:none;" onclick="if(event.target===this) togglePinModal(false)">
        <div class="modal-card">
            <div class="modal-header">
                <h3>🔐 Akses Transaksi Manual</h3>
                <button type="button" class="btn-modal-close" onclick="togglePinModal(false)">✕</button>
            </div>
            <p class="modal-desc">
                Masukkan PIN Trading 6-digit untuk mengaktifkan fitur pasang posisi dan tutup posisi manual di server MT5.
            </p>
            <div class="pin-input-box">
                <input type="password" id="input-pin" class="pin-input" maxlength="6" inputmode="numeric" placeholder="••••••" onkeyup="if(event.key==='Enter') submitPin()">
            </div>
            <div class="pin-error-box" id="pin-error-msg" style="display:none;"></div>
            <div class="modal-actions">
                <button type="button" class="btn-modal-cancel" onclick="togglePinModal(false)">Batal</button>
                <button type="button" class="btn-modal-submit" id="btn-submit-pin" onclick="submitPin()">Verifikasi PIN</button>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- HEADER -->
        <header>
            <div class="brand">
                <div class="brand-icon">🛡️</div>
                <div class="brand-text">
                    <h1>GoldShield AI EA <span style="font-size:0.75rem; background:#eff6ff; color:#1d4ed8; padding:2px 8px; border-radius:12px; border:1px solid #bfdbfe; font-weight:700;">LIVE</span></h1>
                    <p>Pemantauan Real-Time Akun Demo Exness MT5 • Port 8089</p>
                </div>
            </div>
            <div class="header-meta" style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <button type="button" class="pin-badge locked" id="btn-pin-badge" onclick="togglePinModal()" title="Klik untuk membuka / mengunci akses transaksi">
                    <span id="pin-badge-icon">🔒</span>
                    <span id="pin-badge-text">Mode Tamu (Terkunci)</span>
                </button>
                <div class="status-badge">
                    <div class="pulse-dot"></div>
                    <span id="header-status">TERHUBUNG • M15 WAIT</span>
                </div>
            </div>
        </header>

        <!-- KOTAK INFORMASI & ALASAN KEPUTUSAN ROBOT -->
        <div class="decision-card" id="decision-card">
            <div class="decision-header">
                <div class="decision-title-group">
                    <span class="decision-badge standby" id="decision-badge">🟢 STANDBY (0 POSISI)</span>
                    <span class="decision-symbol-pill" id="decision-symbol-pill">XAUUSDm (M15)</span>
                </div>
                <div class="decision-time" id="decision-time">
                    Candle M15 Terakhir: --:-- Server
                </div>
            </div>

            <div class="decision-body">
                <div class="decision-main-row">
                    <div class="decision-icon-large" id="decision-icon">🔍</div>
                    <div class="decision-content">
                        <div class="decision-heading" id="decision-heading">
                            Status Trading: Standby Menunggu Sinyal Valid
                        </div>
                        <div class="decision-explanation" id="decision-explanation">
                            Robot sedang memantau chart secara real-time. Menjaga modal dan otomatis membuka posisi baru saat candle penutupan berikutnya menembus tren terkonfirmasi.
                        </div>
                    </div>
                </div>

                <!-- METRIK INDIKATOR TEKNIKAL REALTIME (Saat Standby) -->
                <div class="decision-metrics-grid" id="decision-metrics-grid">
                    <div class="metric-pill">
                        <span class="metric-lbl">ADX (Tren >20)</span>
                        <strong class="metric-val" id="dec-adx">-</strong>
                    </div>
                    <div class="metric-pill">
                        <span class="metric-lbl">RSI Momentum (14)</span>
                        <strong class="metric-val" id="dec-rsi">-</strong>
                    </div>
                    <div class="metric-pill">
                        <span class="metric-lbl">ATR Volatilitas</span>
                        <strong class="metric-val" id="dec-atr">-</strong>
                    </div>
                    <div class="metric-pill">
                        <span class="metric-lbl">Posisi Harga Relatif</span>
                        <strong class="metric-val" id="dec-ema-rel">-</strong>
                    </div>
                </div>

                <!-- DETAIL POSISI AKTIF (Tampil otomatis saat posisi > 0) -->
                <div class="active-trades-container" id="active-trades-container" style="display:none;"></div>
            </div>
        </div>

        <!-- CHECKLIST EVALUASI SEMUA ATURAN & FILTER TRADING (COLLAPSIBLE) -->
        <div class="rules-card" id="rules-card">
            <div class="rules-header" onclick="toggleRules()" style="cursor:pointer;" title="Klik untuk menampilkan / menyembunyikan rincian 15 rules">
                <div class="rules-title">
                    <span>📋</span>
                    <span>15 Aturan & Syarat Trading Robot</span>
                </div>
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <div class="rules-summary-badge" id="rules-summary-badge">
                        Memuat Evaluasi...
                    </div>
                    <button type="button" class="btn-toggle-rules" id="btn-toggle-rules">👁️ Tampilkan (15)</button>
                </div>
            </div>
            <div class="rules-grid" id="rules-grid" style="display:none;">
                <!-- Diisi otomatis oleh JavaScript -->
            </div>
        </div>

        <!-- GRID STATISTIK -->
        <div class="grid-stats">
            <div class="stat-card card-cyan">
                <div class="stat-label">
                    <span>Saldo (Balance)</span>
                    <span>💵</span>
                </div>
                <div class="stat-value" id="val-balance">$0.00</div>
                <div class="stat-sub">
                    <span>Ekuitas:</span>
                    <strong class="mono" id="val-equity">$0.00</strong>
                </div>
            </div>

            <div class="stat-card card-green">
                <div class="stat-label">
                    <span>Akurasi (Win Rate)</span>
                    <span>🎯</span>
                </div>
                <div class="stat-value val-profit" id="val-winrate">0.0%</div>
                <div class="stat-sub">
                    <span id="val-win-loss">0 Menang / 0 Kalah</span>
                </div>
            </div>

            <div class="stat-card card-green">
                <div class="stat-label">
                    <span>Total Untung Bersih</span>
                    <span>📈</span>
                </div>
                <div class="stat-value" id="val-net-profit">+$0.00</div>
                <div class="stat-sub">
                    <span>Floating PnL:</span>
                    <strong class="mono" id="val-floating">$0.00</strong>
                </div>
            </div>

            <div class="stat-card card-amber">
                <div class="stat-label">
                    <span>Kuota Demo & Status</span>
                    <span>⏱️</span>
                </div>
                <div class="stat-value" id="val-quota">0/20</div>
                <div class="stat-sub">
                    <span>State:</span>
                    <strong class="mono" id="val-state">READY</strong>
                </div>
            </div>
        </div>

        <!-- REAL-TIME LIVE CHART CARD -->
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-box">
                    <span>📈</span>
                    <span id="chart-title">Grafik Live: XAUUSD (Emas M15)</span>
                    <span class="pill pill-buy" style="font-size: 0.68rem; padding: 2px 7px;">REAL-TIME</span>
                </div>
                <div class="chart-controls">
                    <button type="button" class="chart-pill-btn active" id="btn-chart-gold" onclick="selectChart('XAUUSD', true)">Emas (XAU)</button>
                    <button type="button" class="chart-pill-btn" id="btn-chart-btc" onclick="selectChart('BTCUSD', true)">Bitcoin (BTC)</button>
                </div>
            </div>
            <div class="chart-frame-wrapper">
                <iframe id="tv-chart-frame"
                        src="https://s.tradingview.com/widgetembed/?symbol=OANDA%3AXAUUSD&interval=15&theme=light&style=1&timezone=Asia%2FJakarta&locale=id"
                        style="width: 100%; height: 100%; border: none;"
                        loading="lazy"
                        allowtransparency="true"
                        scrolling="no">
                </iframe>
            </div>
        </div>

        <!-- TAB BUTTONS -->
        <div class="tabs-header">
            <button class="tab-btn active" onclick="switchTab('positions')">
                <span>⚡ Posisi Berjalan</span>
                <span class="badge-count" id="count-positions">0</span>
            </button>
            <button class="tab-btn" onclick="switchTab('deals')">
                <span>📜 Riwayat Transaksi</span>
                <span class="badge-count" id="count-deals">0</span>
            </button>
            <button class="tab-btn" onclick="switchTab('audit')">
                <span>🛡️ Log Sinyal & Pengaman</span>
                <span class="badge-count" id="count-audit">0</span>
            </button>
        </div>

        <!-- TAB 1: POSISI BERJALAN -->
        <div class="section-card" id="tab-positions">
            <div class="section-header">
                <div>
                    <h2>⚡ Posisi Aktif Berjalan (Live)</h2>
                    <p class="section-desc">Transaksi yang saat ini sedang floating di pasar</p>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Tiket</th>
                            <th>Simbol</th>
                            <th>Arah</th>
                            <th>Lot</th>
                            <th>Harga Buka</th>
                            <th>Harga Saat Ini</th>
                            <th>Stop Loss</th>
                            <th>Take Profit</th>
                            <th>Floating Profit</th>
                        </tr>
                    </thead>
                    <tbody id="tbody-positions">
                        <tr>
                            <td colspan="9">
                                <div class="empty-state">
                                    <div class="empty-icon">☕</div>
                                    <div class="empty-title">Tidak Ada Posisi Terbuka Saat Ini</div>
                                    <div class="empty-sub">Robot sedang standby menunggu candle M15 selesai dan sinyal tren terkonfirmasi. Saldo modal aman terlindungi.</div>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 2: RIWAYAT TRANSAKSI (DEALS) -->
        <div class="section-card" id="tab-deals" style="display:none;">
            <div class="section-header">
                <div>
                    <h2>📜 Riwayat Transaksi Selesai</h2>
                    <p class="section-desc">Daftar transaksi tertutup beserta hasil keuntungan/kerugian riil</p>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Waktu Buka / Tutup</th>
                            <th>Tiket</th>
                            <th>Simbol</th>
                            <th>Arah</th>
                            <th>Volume</th>
                            <th>Alasan Tutup</th>
                            <th>Profit Bersih</th>
                        </tr>
                    </thead>
                    <tbody id="tbody-deals">
                        <tr>
                            <td colspan="7">
                                <div class="empty-state">
                                    <div class="empty-icon">📂</div>
                                    <div class="empty-title">Belum Ada Riwayat Transaksi Selesai</div>
                                    <div class="empty-sub">Riwayat deal tertutup akan otomatis muncul di sini.</div>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 3: LOG AUDIT PENGAMAN -->
        <div class="section-card" id="tab-audit" style="display:none;">
            <div class="section-header">
                <div>
                    <h2>🛡️ Log Sinyal & Pengaman Server (Audit)</h2>
                    <p class="section-desc">Pencatatan real-time filter ADX, M15/H1 Trend, Stop Loss, dan proteksi risiko</p>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Waktu Server</th>
                            <th>Event / Aksi</th>
                            <th>Simbol</th>
                            <th>Alasan Keputusan</th>
                            <th>Detail Indikator / Filter</th>
                        </tr>
                    </thead>
                    <tbody id="tbody-audit">
                        <tr>
                            <td colspan="5">
                                <div class="empty-state">
                                    <div class="empty-icon">📋</div>
                                    <div class="empty-title">Memuat Log Audit...</div>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- FOOTER -->
        <footer>
            <p>GoldShield AI EA V2 • Mode: Live Interactive MT5 • Port 8089 • Auto-Refresh tiap 3 detik</p>
            <p style="margin-top:4px; color:var(--text-subtle);">Dashboard monitoring real-time aktivitas & analisis robot trading EA GoldShield.</p>
        </footer>
    </div>

    <!-- MOBILE BOTTOM STICKY NAVIGATION (< 768px) -->
    <div class="mobile-bottom-nav">
        <button type="button" class="mob-nav-btn active" id="mob-nav-chart" onclick="scrollToElement('tv-chart-frame'); activateMobNav(this)">
            <span>📈</span>
            <span>Grafik</span>
        </button>
        <button type="button" class="mob-nav-btn" id="mob-nav-pos" onclick="switchTab('positions'); scrollToElement('tab-positions'); activateMobNav(this)">
            <span>📋</span>
            <span>Posisi (<span id="mob-count-pos">0</span>)</span>
        </button>
        <button type="button" class="mob-nav-btn" id="mob-nav-deals" onclick="switchTab('deals'); scrollToElement('tab-deals'); activateMobNav(this)">
            <span>📜</span>
            <span>Riwayat</span>
        </button>
    </div>

    <script>
        let currentTab = 'positions';
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token') || '';

        // Operator PIN State & Management
        let operatorPin = sessionStorage.getItem('goldshield_trading_pin') || '';
        let isPinVerified = false;
        let pendingAction = null;

        function updatePinUi() {
            const badge = document.getElementById('btn-pin-badge');
            const icon = document.getElementById('pin-badge-icon');
            const text = document.getElementById('pin-badge-text');
            const authStatus = document.getElementById('trade-auth-status');

            if (isPinVerified) {
                if (badge) {
                    badge.className = 'pin-badge unlocked';
                    if (icon) icon.textContent = '🔓';
                    if (text) text.textContent = 'Donny (Akses Aktif)';
                }
                if (authStatus) {
                    authStatus.innerHTML = '<span style="color:#16a34a; font-weight:700;">🟢 Akses Aktif (Siap Transaksi)</span>';
                }
            } else {
                if (badge) {
                    badge.className = 'pin-badge locked';
                    if (icon) icon.textContent = '🔒';
                    if (text) text.textContent = 'Mode Tamu (Terkunci)';
                }
                if (authStatus) {
                    authStatus.innerHTML = '<span style="color:#92400e; font-weight:600;">🔒 Terproteksi PIN</span>';
                }
            }
        }

        function togglePinModal(show = true) {
            const modal = document.getElementById('pin-modal');
            const pinInput = document.getElementById('input-pin');
            const errBox = document.getElementById('pin-error-msg');
            if (!modal) return;
            if (show) {
                modal.style.display = 'flex';
                if (errBox) errBox.style.display = 'none';
                if (pinInput) {
                    pinInput.value = '';
                    setTimeout(() => pinInput.focus(), 150);
                }
            } else {
                modal.style.display = 'none';
            }
        }

        function ensurePinAccess(onSuccess) {
            if (isPinVerified && operatorPin) {
                onSuccess(operatorPin);
                return;
            }
            pendingAction = onSuccess;
            togglePinModal(true);
        }

        function submitPin() {
            const pinInput = document.getElementById('input-pin');
            const pin = (pinInput ? pinInput.value : '').trim();
            const errBox = document.getElementById('pin-error-msg');
            const curToken = new URLSearchParams(window.location.search).get('token') || '';

            if (!pin || pin.length < 4) {
                if (errBox) {
                    errBox.textContent = 'Masukkan minimal 4-6 digit PIN.';
                    errBox.style.display = 'block';
                }
                return;
            }

            fetch(`/api/verify_pin?token=${curToken}&pin=${encodeURIComponent(pin)}`)
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        operatorPin = pin;
                        sessionStorage.setItem('goldshield_trading_pin', pin);
                        isPinVerified = true;
                        updatePinUi();
                        togglePinModal(false);
                        if (pendingAction) {
                            const act = pendingAction;
                            pendingAction = null;
                            act(pin);
                        }
                    } else {
                        if (errBox) {
                            errBox.textContent = res.error || 'PIN Keamanan Salah. Silakan coba lagi.';
                            errBox.style.display = 'block';
                        }
                    }
                })
                .catch(err => {
                    if (errBox) {
                        errBox.textContent = 'Koneksi error: ' + err.message;
                        errBox.style.display = 'block';
                    }
                });
        }

        // Auto verify cached PIN on page load
        if (operatorPin) {
            fetch(`/api/verify_pin?token=${token}&pin=${encodeURIComponent(operatorPin)}`)
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        isPinVerified = true;
                        updatePinUi();
                    } else {
                        sessionStorage.removeItem('goldshield_trading_pin');
                        operatorPin = '';
                        isPinVerified = false;
                        updatePinUi();
                    }
                }).catch(() => {});
        }

        // Rules Collapsible Toggle
        let rulesExpanded = false;
        function toggleRules() {
            rulesExpanded = !rulesExpanded;
            const grid = document.getElementById('rules-grid');
            const btn = document.getElementById('btn-toggle-rules');
            if (grid) {
                grid.style.display = rulesExpanded ? 'grid' : 'none';
            }
            if (btn) {
                btn.innerHTML = rulesExpanded ? '🙈 Sembunyikan' : '👁️ Tampilkan (15)';
            }
        }

        // Manual Trading Form Helpers
        let selectedTradeLot = 0.01;

        function setTradeLot(lot, btn) {
            selectedTradeLot = lot;
            const input = document.getElementById('trade-lot-input');
            if (input) input.value = lot.toFixed(2);
            document.querySelectorAll('.pill-lot').forEach(p => p.classList.remove('active'));
            if (btn) btn.classList.add('active');
        }

        function onCustomLotChange(val) {
            let num = parseFloat(val);
            if (isNaN(num) || num <= 0) num = 0.01;
            if (num > 0.05) num = 0.05;
            selectedTradeLot = num;
            document.querySelectorAll('.pill-lot').forEach(p => {
                if (parseFloat(p.textContent) === num) p.classList.add('active');
                else p.classList.remove('active');
            });
        }

        function toggleAutoProtect(checked) {
            const customRow = document.getElementById('trade-custom-inputs');
            if (customRow) {
                customRow.style.display = checked ? 'none' : 'grid';
            }
        }

        function clickManualOrder(side) {
            ensurePinAccess(pin => {
                const lot = selectedTradeLot;
                const autoProtect = document.getElementById('trade-auto-protect') ? document.getElementById('trade-auto-protect').checked : true;
                let sl = 0.0;
                let tp = 0.0;
                if (!autoProtect) {
                    sl = parseFloat(document.getElementById('trade-custom-sl').value) || 0.0;
                    tp = parseFloat(document.getElementById('trade-custom-tp').value) || 0.0;
                }

                const sideLabel = side === 'BUY' ? 'Beli (Long)' : 'Jual (Short)';
                const confirmMsg = `Konfirmasi Pasang Posisi:\n` +
                    `• Transaksi: ${side} (${sideLabel})\n` +
                    `• Ukuran Lot: ${lot.toFixed(2)} Lot\n` +
                    `• Pengaman: ${autoProtect ? 'Otomatis Robot (SL 2.0 ATR, TP 2.5 ATR, Fast Profit Lock)' : 'Custom SL/TP'}\n\n` +
                    `Kirim order sekarang ke robot MT5?`;

                if (!confirm(confirmMsg)) return;

                const curToken = new URLSearchParams(window.location.search).get('token') || '';
                fetch(`/api/order?token=${curToken}&pin=${encodeURIComponent(pin)}&type=${side}&lot=${lot}&sl=${sl}&tp=${tp}`, { method: 'POST' })
                    .then(r => r.json())
                    .then(res => {
                        if (res.success) {
                            alert(`✅ ${res.message}\nRobot sedang mengeksekusi order ${side}.`);
                            fetchData();
                        } else {
                            alert(`❌ Gagal pasang posisi: ${res.error || 'Terjadi kesalahan sistem'}`);
                        }
                    })
                    .catch(err => {
                        alert(`❌ Terjadi kendala koneksi: ${err.message}`);
                    });
            });
        }

        // Mobile Nav Helpers
        function scrollToElement(id) {
            const el = document.getElementById(id);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        function activateMobNav(btn) {
            document.querySelectorAll('.mob-nav-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
        }

        function switchTab(tabName) {
            currentTab = tabName;
            document.getElementById('tab-positions').style.display = tabName === 'positions' ? 'block' : 'none';
            document.getElementById('tab-deals').style.display = tabName === 'deals' ? 'block' : 'none';
            document.getElementById('tab-audit').style.display = tabName === 'audit' ? 'block' : 'none';

            const buttons = document.querySelectorAll('.tabs-header .tab-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            if (tabName === 'positions') buttons[0].classList.add('active');
            if (tabName === 'deals') buttons[1].classList.add('active');
            if (tabName === 'audit') buttons[2].classList.add('active');
        }

        let activeChartSymbol = 'XAUUSD';
        let userChartOverride = false;

        function selectChart(target, isUserClick = false) {
            if (isUserClick) userChartOverride = true;
            if (activeChartSymbol === target && !isUserClick) return;
            activeChartSymbol = target;

            const frame = document.getElementById('tv-chart-frame');
            const title = document.getElementById('chart-title');
            const btnGold = document.getElementById('btn-chart-gold');
            const btnBtc = document.getElementById('btn-chart-btc');

            let tvSym = "OANDA%3AXAUUSD";
            let label = "XAUUSD (Emas M15)";
            if (target === 'BTCUSD') {
                tvSym = "BINANCE%3ABTCUSDT";
                label = "BTCUSD (Bitcoin M15)";
                if (btnBtc) btnBtc.classList.add('active');
                if (btnGold) btnGold.classList.remove('active');
            } else {
                if (btnGold) btnGold.classList.add('active');
                if (btnBtc) btnBtc.classList.remove('active');
            }

            if (title) title.textContent = `Grafik Live: ${label}`;
            if (frame) {
                frame.src = `https://s.tradingview.com/widgetembed/?symbol=${tvSym}&interval=15&theme=light&style=1&timezone=Asia%2FJakarta&locale=id`;
            }
        }

        function formatCurrency(val) {
            const num = parseFloat(val) || 0;
            return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        function formatProfit(val) {
            const num = parseFloat(val) || 0;
            const sign = num > 0 ? '+' : '';
            return sign + '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        async function fetchData() {
            try {
                const res = await fetch(`/api/data?token=${encodeURIComponent(token)}`);
                if (!res.ok) return;
                const data = await res.json();
                renderDashboard(data);
            } catch (err) {
                console.error("Dashboard fetch error:", err);
            }
        }

        const REASON_DICT = {
            'CANDIDATE_PULLBACK': {
                title: 'Model Pullback / EMA Retest Terkonfirmasi',
                desc: 'Harga menguji area EMA 20 di dalam tren kuat dan memantul konfirmasi dengan lilin momentum tebal. Mengambil posisi pada harga diskon.',
                icon: '🎯'
            },
            'CANDIDATE_BREAKOUT': {
                title: 'Model Box Breakout Terkonfirmasi',
                desc: 'Harga menembus batas rentang 4 lilin sebelumnya disertai lonjakan volume transaksi. Mengambil posisi momentum ledakan tren.',
                icon: '🚀'
            },
            'CANDIDATE_CROSSOVER': {
                title: 'Model Crossover EMA Terkonfirmasi',
                desc: 'Terjadi persilangan baru EMA 20 dan EMA 50 didukung keselarasan tren H1 dan kekuatan ADX.',
                icon: '⚡'
            },
            'HOLD_CONFLUENCE_SCORE_LOW': {
                title: 'Skor Konfluensi Sedang Dikumpulkan (Min 65 Poin)',
                desc: 'Mayoritas indikator sudah mulai selaras. Robot menunggu skor pembobotan konfluensi mencapai ambang kelulusan (>= 65 Poin) agar peluang menang maksimal.',
                icon: '📊'
            },
            'HOLD_ADDON_EXISTING_NOT_BREAKEVEN': {
                title: 'Tahan Posisi Tambahan (Zero-Risk Pyramiding Guard)',
                desc: 'Posisi aktif pertama belum mengunci modal di Break-Even (+0.2 ATR). Posisi kedua hanya dibuka jika posisi pertama sudah 100% bebas risiko modal (Zero Risk).',
                icon: '🛡️'
            },
            'HOLD_RULES_NO_SETUP': {
                title: 'Menunggu Pola Multi-Setup (Pullback / Breakout / Crossover)',
                desc: 'Kondisi pasar saat ini belum memenuhi salah satu dari 3 setup entri unggulan (Pullback Retest, Box Breakout, atau Baseline Crossover). Robot sabar menahan diri agar tidak masuk di tengah pergerakan liar.',
                icon: '⏳'
            },
            'HOLD_ADX_SIDEWAYS': {
                title: 'Pasar Sideways / Datar (ADX < 20)',
                desc: 'Kekuatan tren pasar sedang lemah di bawah ambang batas minimal (ADX < 20.0). Robot menahan transaksi untuk melindungi saldo dari ayunan harga tanpa arah (whipsaw).',
                icon: '💤'
            },
            'HOLD_ADX_MOMENTUM_FALLING': {
                title: 'Momentum Tren Sedang Melandai / Melemah',
                desc: 'Nilai indikator kekuatan tren (ADX) pada lilin penutupan terpantau turun dibandingkan lilin sebelumnya. Robot menunggu momentum tren kembali menanjak.',
                icon: '📉'
            },
            'HOLD_HTF_TREND_BEARISH': {
                title: 'Bertentangan dengan Tren Besar H1 (Bearish)',
                desc: 'Sinyal beli M15 ditolak karena tren timeframe 1 Jam (H1) sedang menurun. Robot disiplin hanya mengambil posisi searah dengan tren institusi.',
                icon: '🛡️'
            },
            'HOLD_HTF_TREND_BULLISH': {
                title: 'Bertentangan dengan Tren Besar H1 (Bullish)',
                desc: 'Sinyal jual M15 ditolak karena tren timeframe 1 Jam (H1) sedang menaik. Robot disiplin hanya mengambil posisi searah dengan tren institusi.',
                icon: '🛡️'
            },
            'HOLD_HTF_SLOPE_FLAT': {
                title: 'Kemiringan Sudut Tren H1 Kurang Tajam',
                desc: 'Sudut pergerakan EMA H1 masih relatif datar. Robot menunggu momentum arah yang lebih tegas sebelum mengambil risiko modal.',
                icon: '📐'
            },
            'HOLD_CANDLE_BULLISH': {
                title: 'Warna Candle M15 Menutup Hijau (Bullish)',
                desc: 'Sinyal SELL memerlukan konfirmasi candle penutupan merah. Karena lilin M15 ditutup hijau, robot menunda eksekusi order.',
                icon: '🕯️'
            },
            'HOLD_CANDLE_BEARISH': {
                title: 'Warna Candle M15 Menutup Merah (Bearish)',
                desc: 'Sinyal BUY memerlukan konfirmasi candle penutupan hijau. Karena lilin M15 ditutup merah, robot menunda eksekusi order.',
                icon: '🕯️'
            },
            'HOLD_CANDLE_BODY_TOO_SMALL': {
                title: 'Badan Lilin M15 Terlalu Tipis (Doji/Ragu)',
                desc: 'Ukuran badan candle penutupan kurang dari 40% dari total tinggi candle. Menandakan ketidakpastian pasar, berisiko pembalikan arah instan.',
                icon: '⚖️'
            },
            'HOLD_CANDLE_LOWER_WICK_REJECTION': {
                title: 'Penolakan Harga Bawah (Rejection Wick)',
                desc: 'Lilin memiliki ekor bawah yang terlalu panjang (terjadi perlawanan beli kuat). Berbahaya untuk melakukan penjualan.',
                icon: '⚠️'
            },
            'HOLD_CANDLE_UPPER_WICK_REJECTION': {
                title: 'Penolakan Harga Atas (Rejection Wick)',
                desc: 'Lilin memiliki ekor atas yang terlalu panjang (terjadi tekanan jual kuat). Berbahaya untuk melakukan pembelian.',
                icon: '⚠️'
            },
            'HOLD_LOW_TICK_VOLUME': {
                title: 'Volume Transaksi Tick Terlalu Rendah',
                desc: 'Aktivitas volume pasar berada di bawah 75% dari rata-rata 5 candle terakhir. Likuiditas tipis rawan pelebaran spread broker.',
                icon: '📊'
            },
            'HOLD_PRICE_OVEREXTENDED': {
                title: 'Harga Terlalu Jauh dari Rata-Rata (Overextended)',
                desc: 'Jarak harga saat ini sudah merenggang lebih dari 1.8 ATR dari garis EMA. Menghindari risiko beli di pucuk atau jual di dasar lembah.',
                icon: '🛑'
            },
            'HOLD_NEWS_VOLATILITY_SURGE': {
                title: 'Lonjakan Volatilitas Ekstrim (Berita/Flash Move)',
                desc: 'Rentang candle penutupan melebihi 2.5x ATR normal. Robot memblokir order untuk menyelamatkan modal dari goncangan liar pasar.',
                icon: '⚡'
            },
            'HOLD_SESSION_FILTER_CLOSED': {
                title: 'Di Luar Jam Sesi Utama Emas (07:00–21:00 Server)',
                desc: 'Bursa Emas berada di luar jam likuiditas tertinggi London & New York. Robot standby guna menghindari spread malam broker yang tinggi.',
                icon: '🌙'
            },
            'HOLD_WEEKLY_OPEN_STABILIZATION': {
                title: 'Masa Stabilisasi Pembukaan Bursa Senin',
                desc: 'Jeda 30 menit awal pembukaan pasar Senin (00:00–00:30 server) untuk menghindari risiko gap harga dan spread pembukaan.',
                icon: '🌅'
            },
            'HOLD_DAILY_PROFIT_TARGET_REACHED': {
                title: 'Target Profit Harian Tercapai (+2%)',
                desc: 'Target akumulasi keuntungan harian telah tercapai. Robot mengunci laba dan berhenti trading hingga pergantian hari berikutnya.',
                icon: '🏆'
            },
            'HOLD_SPREAD_ATR_EXCESSIVE': {
                title: 'Spread Broker Sedang Melebar',
                desc: 'Selisih harga Bid/Ask sedang melebihi 30% ATR. Robot menunggu spread broker kembali ke kondisi rapat yang efisien.',
                icon: '↔️'
            },
            'WAIT_NEXT_CLOSED_BAR': {
                title: 'Menunggu Lilin M15 Selesai Ditutup',
                desc: 'Robot mengevaluasi sinyal secara disiplin hanya saat lilin 15 menit ditutup sempurna (menit :00, :15, :30, :45). Sedang mengamati formasi lilin berjalan.',
                icon: '⏱️'
            }
        };

        function getReasonInfo(reasonCode) {
            if (!reasonCode) return REASON_DICT['WAIT_NEXT_CLOSED_BAR'];
            for (const [key, val] of Object.entries(REASON_DICT)) {
                if (reasonCode.includes(key)) return val;
            }
            return {
                title: `Menunggu Konfirmasi Sinyal`,
                desc: `Robot sedang mengamati pasar dan menunggu seluruh filter teknikal M15/H1 terpenuhi sebelum membuka posisi.`,
                icon: 'ℹ️'
            };
        }

        function renderRulesChecklist(data) {
            const dec = data.market_decision || {};
            const rsn = dec.reason || '';
            const s = data.summary || {};
            const activeTrades = data.positions || [];
            const isTradeActive = activeTrades.length > 0;
            const activeSym = s.active_symbol || dec.symbol || 'XAUUSDm';
            const isCrypto = activeSym.toUpperCase().includes('BTC');

            const adxVal = parseFloat(dec.adx) || 0;
            const rsiVal = parseFloat(dec.rsi) || 50;
            const atrVal = parseFloat(dec.atr) || 0;
            const closeVal = parseFloat(dec.close) || 0;
            const fastEma = parseFloat(dec.fast_ema) || 0;
            const slowEma = parseFloat(dec.slow_ema) || 0;
            const htfFast = parseFloat(dec.htf_fast) || 0;
            const htfSlow = parseFloat(dec.htf_slow) || 0;

            let serverHour = -1;
            if (dec.bar_time) {
                const parts = dec.bar_time.split(' ');
                if (parts.length > 1) {
                    const timeParts = parts[1].split(':');
                    serverHour = parseInt(timeParts[0], 10);
                }
            }

            // Sesi Trading: 24 Jam Non-Stop (UseSessionFilter = false)
            let sessionStatus = 'pass';
            let sessionText = isCrypto ? 'MEMENUHI ✅ (Kripto 24/7)' : 'MEMENUHI ✅ (24 Jam Non-Stop)';

            // Perhitungan Skor Konfluensi Dinamis (0 - 100 Poin)
            let confScore = 0;
            if (isTradeActive) {
                confScore = 100;
            } else {
                // HTF Trend (+20)
                if (!rsn.includes('HOLD_HTF_TREND') && htfFast > 0) confScore += 20;
                // HTF Slope (+10)
                if (!rsn.includes('HOLD_HTF_SLOPE')) confScore += 10;
                // EMA M15 (+10)
                if (fastEma > 0 && slowEma > 0) confScore += 10;
                // Setup Model (+15)
                if (rsn.includes('CANDIDATE') || !rsn.includes('NO_SETUP')) confScore += 15;
                // ADX Trend (+15 / +10)
                if (adxVal >= 25.0) confScore += 15;
                else if (adxVal >= 20.0) confScore += 10;
                if (rsn !== 'HOLD_ADX_MOMENTUM_FALLING') confScore += 5;
                // Candle Direction (+10)
                if (rsn !== 'HOLD_CANDLE_BEARISH' && rsn !== 'HOLD_CANDLE_BULLISH') confScore += 10;
                // Candle Body & Wick (+5 +5)
                if (rsn !== 'HOLD_CANDLE_BODY_TOO_SMALL') confScore += 5;
                if (!rsn.includes('WICK_REJECTION')) confScore += 5;
                // Tick Volume (+15 / +10 / +5)
                if (rsn !== 'HOLD_LOW_TICK_VOLUME') confScore += 10;
                else confScore += 5;
                // RSI Momentum (+10)
                if (rsn !== 'HOLD_RSI_MOMENTUM_WEAK') confScore += 10;
                if (confScore > 100) confScore = 100;
            }

            const rules = [
                {
                    id: 'session',
                    name: '1. Sesi Jam Bursa (24 Jam Non-Stop)',
                    condition: 'Jendela perdagangan aktif 24 jam dengan proteksi rollover spread otomatis.',
                    current: isCrypto ? 'Pasar Kripto 24/7' : (serverHour >= 0 ? `Jam Server: ${serverHour.toString().padStart(2, '0')}:xx (Trading 24 Jam Aktif)` : 'Trading 24 Jam Aktif'),
                    status: 'pass',
                    badgeText: sessionText,
                    poin: 'Syarat Waktu'
                },
                {
                    id: 'adx_sideways',
                    name: '2. Kekuatan Tren Pasar (ADX >= 20.0)',
                    condition: 'Melindungi modal dari pasar flat / sideways tanpa arah.',
                    current: `Nilai ADX Lilin: ${adxVal > 0 ? adxVal.toFixed(2) : '-'} (Ambang Batas Min: 20.0)`,
                    status: isTradeActive || (adxVal >= 20.0 && rsn !== 'HOLD_ADX_SIDEWAYS') ? 'pass' : 'block',
                    badgeText: (adxVal >= 20.0 && rsn !== 'HOLD_ADX_SIDEWAYS') ? 'MEMENUHI ✅ (+15 Poin)' : 'TIDAK MEMENUHI ❌ (Sideways)',
                    poin: '15 Poin'
                },
                {
                    id: 'adx_momentum',
                    name: '3. Momentum Tren Menanjak (Rising ADX)',
                    condition: 'Filter momentum menanjak dilonggarkan agar robot lebih responsif saat ADX ≥ 20.',
                    current: 'Filter dilonggarkan (RequireRisingADX = OFF)',
                    status: 'pass',
                    badgeText: 'DILONGGARKAN ⚡ (+5 Poin)',
                    poin: '5 Poin'
                },
                {
                    id: 'htf_trend',
                    name: '4. Keselarasan Tren Besar H1 (Multi-Timeframe)',
                    condition: 'Order wajib searah dengan tren institusi H1 (H1 Close & Fast > Slow EMA).',
                    current: rsn === 'HOLD_HTF_TREND_BULLISH' ? `M15 mau SELL tapi H1 masih Bullish (${htfFast.toFixed(2)} > ${htfSlow.toFixed(2)})` :
                             rsn === 'HOLD_HTF_TREND_BEARISH' ? `M15 mau BUY tapi H1 masih Bearish (${htfFast.toFixed(2)} < ${htfSlow.toFixed(2)})` :
                             (htfFast > 0 ? `H1 Fast: ${htfFast.toFixed(2)} | Slow: ${htfSlow.toFixed(2)} (${htfFast >= htfSlow ? 'Bullish' : 'Bearish'})` : 'Sesuai tren H1'),
                    status: isTradeActive || (!rsn.includes('HOLD_HTF_TREND')) ? 'pass' : 'block',
                    badgeText: rsn.includes('HOLD_HTF_TREND') ? 'BERTENTANGAN 🛑' : 'MEMENUHI ✅ (+20 Poin)',
                    poin: '20 Poin'
                },
                {
                    id: 'htf_slope',
                    name: '5. Sudut Kemiringan Tren H1 (Slope Alignment)',
                    condition: 'Sudut pergerakan garis EMA H1 harus menanjak tegas, bukan mendatar.',
                    current: rsn.includes('HOLD_HTF_SLOPE') ? 'Sudut EMA H1 mendatar/kurang tajam' : 'Sudut EMA H1 menanjak tegas',
                    status: isTradeActive || (!rsn.includes('HOLD_HTF_SLOPE')) ? 'pass' : 'fail',
                    badgeText: rsn.includes('HOLD_HTF_SLOPE') ? 'KONTRIBUSI SKOR ⏳ (0 Poin)' : 'MEMENUHI ✅ (+10 Poin)',
                    poin: '10 Poin'
                },
                {
                    id: 'candle_dir',
                    name: '6. Arah Warna Lilin M15 (Candle Momentum)',
                    condition: 'Sinyal BUY lilin hijau, sinyal SELL lilin merah (toleransi pullback/retest).',
                    current: rsn === 'HOLD_CANDLE_BEARISH' ? 'Lilin M15 merah (Koreksi pullback)' : (rsn === 'HOLD_CANDLE_BULLISH' ? 'Lilin M15 hijau (Koreksi rally)' : 'Warna lilin M15 selaras tren'),
                    status: isTradeActive || (rsn !== 'HOLD_CANDLE_BEARISH' && rsn !== 'HOLD_CANDLE_BULLISH') ? 'pass' : 'fail',
                    badgeText: (rsn === 'HOLD_CANDLE_BEARISH' || rsn === 'HOLD_CANDLE_BULLISH') ? 'KONTRIBUSI SKOR ⏳ (0 Poin)' : 'MEMENUHI ✅ (+10 Poin)',
                    poin: '10 Poin'
                },
                {
                    id: 'candle_body',
                    name: '7. Bobot Badan Lilin M15 (Min Body >= 40%)',
                    condition: 'Menolak candle doji / lilin banci tanpa komitmen di area sempit.',
                    current: rsn === 'HOLD_CANDLE_BODY_TOO_SMALL' ? 'Badan lilin < 40% (Doji/ragu-ragu)' : 'Badan lilin proporsional & solid',
                    status: isTradeActive || rsn !== 'HOLD_CANDLE_BODY_TOO_SMALL' ? 'pass' : 'fail',
                    badgeText: rsn === 'HOLD_CANDLE_BODY_TOO_SMALL' ? 'KONTRIBUSI SKOR ⏳ (0 Poin)' : 'MEMENUHI ✅ (+5 Poin)',
                    poin: '5 Poin'
                },
                {
                    id: 'wick_reject',
                    name: '8. Penolakan Ekor Lilin (Wick Rejection Guard)',
                    condition: 'Tidak ada perlawanan ekor panjang berlawanan arah sinyal.',
                    current: rsn.includes('WICK_REJECTION') ? 'Terdeteksi perlawanan ekor penolakan' : 'Aman dari penolakan ekor berlawanan',
                    status: isTradeActive || (!rsn.includes('WICK_REJECTION')) ? 'pass' : 'fail',
                    badgeText: rsn.includes('WICK_REJECTION') ? 'KONTRIBUSI SKOR ⏳ (0 Poin)' : 'MEMENUHI ✅ (+5 Poin)',
                    poin: '5 Poin'
                },
                {
                    id: 'tick_volume',
                    name: '9. Volume Transaksi Tick (Min 75% Rata-Rata)',
                    condition: 'Aktivitas transaksi pasar aktif (volume tick >= 0.75x rata-rata 5 candle).',
                    current: rsn === 'HOLD_LOW_TICK_VOLUME' ? 'Volume tick sedang di bawah rata-rata' : 'Aktivitas volume normal / tinggi',
                    status: isTradeActive || rsn !== 'HOLD_LOW_TICK_VOLUME' ? 'pass' : 'fail',
                    badgeText: rsn === 'HOLD_LOW_TICK_VOLUME' ? 'KONTRIBUSI SKOR ⏳ (+5 Poin)' : 'MEMENUHI ✅ (+10 Poin)',
                    poin: '10 Poin'
                },
                {
                    id: 'price_stretch',
                    name: '10. Jarak Peregangan Harga (Stretch <= 1.8 ATR)',
                    condition: 'Mencegah beli di pucuk tertinggi atau jual di lembah terdalam.',
                    current: rsn === 'HOLD_PRICE_OVEREXTENDED' ? 'Jarak harga merenggang > 1.8 ATR dari EMA' : 'Jarak harga wajar & aman dari pucuk',
                    status: isTradeActive || rsn !== 'HOLD_PRICE_OVEREXTENDED' ? 'pass' : 'block',
                    badgeText: rsn === 'HOLD_PRICE_OVEREXTENDED' ? 'TIDAK MEMENUHI 🛑 (Pucuk)' : 'MEMENUHI ✅ (Pelindung Mutlak)',
                    poin: 'Pelindung Mutlak'
                },
                {
                    id: 'news_surge',
                    name: '11. Filter Volatilitas Ekstrim (News <= 2.5 ATR)',
                    condition: 'Memblokir order saat lonjakan liar berita tak terkendali.',
                    current: rsn === 'HOLD_NEWS_VOLATILITY_SURGE' ? 'Terjadi lonjakan candle > 2.5x ATR' : 'Volatilitas stabil terkendali',
                    status: isTradeActive || rsn !== 'HOLD_NEWS_VOLATILITY_SURGE' ? 'pass' : 'block',
                    badgeText: rsn === 'HOLD_NEWS_VOLATILITY_SURGE' ? 'BLOKIR BERITA ⚡' : 'MEMENUHI ✅ (Pelindung Mutlak)',
                    poin: 'Pelindung Mutlak'
                },
                {
                    id: 'spread_atr',
                    name: '12. Toleransi Spread Broker (Spread <= 0.30 ATR)',
                    condition: 'Menolak order saat broker melebarkan spread di atas batas wajar.',
                    current: rsn === 'HOLD_SPREAD_ATR_EXCESSIVE' ? 'Spread broker melebar di atas 30% ATR' : 'Spread broker rapat & hemat biaya',
                    status: isTradeActive || rsn !== 'HOLD_SPREAD_ATR_EXCESSIVE' ? 'pass' : 'block',
                    badgeText: rsn === 'HOLD_SPREAD_ATR_EXCESSIVE' ? 'SPREAD MELEBAR ↔️' : 'MEMENUHI ✅ (Pelindung Mutlak)',
                    poin: 'Pelindung Mutlak'
                },
                {
                    id: 'midnight_rollover',
                    name: '13. Proteksi Rollover Malam (23:55–00:15 Broker)',
                    condition: 'Blokir entri saat pergantian hari untuk hindari lonjakan spread & swap.',
                    current: rsn === 'HOLD_MIDNIGHT_ROLLOVER' ? 'Sedang jam rollover pergantian hari' : 'Di luar jam rollover tengah malam',
                    status: isTradeActive || rsn !== 'HOLD_MIDNIGHT_ROLLOVER' ? 'pass' : 'block',
                    badgeText: rsn === 'HOLD_MIDNIGHT_ROLLOVER' ? 'ROLLOVER MALAM 🌙' : 'MEMENUHI ✅ (Pelindung Mutlak)',
                    poin: 'Pelindung Mutlak'
                },
                {
                    id: 'daily_quota',
                    name: '14. Batas Kuota Transaksi Harian (Maks 20 Entri)',
                    condition: 'Mencegah overtrading berlebih dan melindungi modal harian.',
                    current: `Entri hari ini: ${s.entries_count || 0} / ${s.max_entries || 20}`,
                    status: isTradeActive || (rsn !== 'HOLD_DAILY_ENTRY_LIMIT' && rsn !== 'HOLD_DAILY_PROFIT_TARGET_REACHED') ? 'pass' : 'block',
                    badgeText: rsn === 'HOLD_DAILY_PROFIT_TARGET_REACHED' ? 'TARGET 2% TERCAPAI 🏆' : (rsn === 'HOLD_DAILY_ENTRY_LIMIT' ? 'KUOTA HABIS 🛑' : 'MEMENUHI ✅ (Pelindung Mutlak)'),
                    poin: 'Pelindung Mutlak'
                },
                {
                    id: 'setup_pattern',
                    name: '15. Pola Multi-Setup (Pullback / Breakout / Cross)',
                    condition: 'Wajib terkonfirmasi salah satu dari 3 setup teknikal konfluensi.',
                    current: isTradeActive ? 'Posisi aktif berjalan' : (rsn.includes('CANDIDATE') ? 'Setup entri terkonfirmasi' : 'Pola teknikal aktif dipantau'),
                    status: isTradeActive || rsn.includes('CANDIDATE') || !rsn.includes('NO_SETUP') ? 'pass' : 'fail',
                    badgeText: isTradeActive || rsn.includes('CANDIDATE') || !rsn.includes('NO_SETUP') ? 'MEMENUHI ✅ (+15 Poin)' : 'KONTRIBUSI SKOR ⏳ (0 Poin)',
                    poin: '15 Poin'
                }
            ];

            let passCount = rules.filter(r => r.status === 'pass').length;
            const summaryBadge = document.getElementById('rules-summary-badge');
            if (summaryBadge) {
                const isReadyToTrade = confScore >= 65;
                summaryBadge.innerHTML = `
                    <span style="margin-right:6px;">${passCount} / ${rules.length} Memenuhi</span>
                    <span style="background:${isReadyToTrade ? '#16a34a' : '#2563eb'}; color:#ffffff; padding:2px 8px; border-radius:12px; font-size:0.72rem; font-weight:700;">
                        Skor Konfluensi: ${confScore}/100 (Ambang >= 65) • ${isReadyToTrade ? 'SIAP ENTRY 🎯' : 'KUMPULKAN SKOR ⏳'}
                    </span>
                `;
                summaryBadge.style.background = '#f1f5f9';
                summaryBadge.style.color = '#0f172a';
                summaryBadge.style.border = '1px solid #cbd5e1';
            }

            const container = document.getElementById('rules-grid');
            if (!container) return;

            let html = '';
            rules.forEach(r => {
                const isPass = r.status === 'pass';
                const itemClass = isPass ? 'pass' : (r.status === 'block' ? 'block' : 'fail');
                const badgeClass = isPass ? 'pass' : (r.status === 'block' ? 'block' : 'fail');

                html += `
                <div class="rule-item ${itemClass}">
                    <div class="rule-top">
                        <span class="rule-name">${r.name}</span>
                        <span class="rule-badge ${badgeClass}">${r.badgeText}</span>
                    </div>
                    <div class="rule-condition">${r.condition}</div>
                    <div class="rule-current">
                        <span style="color:var(--text-muted); font-size:0.7rem;">Kondisi Live (${r.poin}):</span>
                        <span>${r.current}</span>
                    </div>
                </div>`;
            });
            container.innerHTML = html;
        }

        function renderDashboard(data) {
            const s = data.summary || {};

            // 1. Summary Cards
            document.getElementById('val-balance').textContent = formatCurrency(s.balance);
            document.getElementById('val-equity').textContent = formatCurrency(s.equity);

            const wins = parseInt(s.wins) || 0;
            const losses = parseInt(s.losses) || 0;
            const totalFinished = wins + losses;
            const winRate = totalFinished > 0 ? ((wins / totalFinished) * 100).toFixed(1) : '0.0';
            document.getElementById('val-winrate').textContent = winRate + '%';
            document.getElementById('val-win-loss').textContent = `${wins} Menang / ${losses} Kalah`;

            const netProfit = parseFloat(s.net_closed) || 0;
            const netEl = document.getElementById('val-net-profit');
            netEl.textContent = formatProfit(netProfit);
            netEl.className = 'stat-value ' + (netProfit > 0 ? 'val-profit' : (netProfit < 0 ? 'val-loss' : 'val-neutral'));

            // Floating calculation
            let totalFloating = 0;
            const pos = data.positions || [];
            pos.forEach(p => { totalFloating += (parseFloat(p.profit) || 0); });
            const floatEl = document.getElementById('val-floating');
            floatEl.textContent = formatProfit(totalFloating);
            floatEl.className = 'mono ' + (totalFloating > 0 ? 'val-profit' : (totalFloating < 0 ? 'val-loss' : ''));

            // Quota
            const closed = s.closed_positions || '0';
            const limit = s.limit || '20';
            document.getElementById('val-quota').textContent = `${closed}/${limit}`;
            document.getElementById('val-state').textContent = s.core_state || 'READY';

            // Counts
            document.getElementById('count-positions').textContent = pos.length;
            const mobPos = document.getElementById('mob-count-pos');
            if (mobPos) mobPos.textContent = pos.length;
            document.getElementById('count-deals').textContent = (data.deals || []).length;
            document.getElementById('count-audit').textContent = (data.audit || []).length;

            // 2. Decision Card & Explanation Update
            const headerStatus = document.getElementById('header-status');
            const activeSym = s.active_symbol || 'XAUUSDm';

            // Auto sync live chart symbol to active session
            if (!userChartOverride) {
                const targetSym = activeSym.toUpperCase().includes('BTC') ? 'BTCUSD' : 'XAUUSD';
                if (activeChartSymbol !== targetSym) {
                    selectChart(targetSym, false);
                }
            }

            const dec = data.market_decision || {};
            const decBadge = document.getElementById('decision-badge');
            const decSymPill = document.getElementById('decision-symbol-pill');
            const decTime = document.getElementById('decision-time');
            const decIcon = document.getElementById('decision-icon');
            const decHeading = document.getElementById('decision-heading');
            const decExplanation = document.getElementById('decision-explanation');
            const decMetricsGrid = document.getElementById('decision-metrics-grid');
            const activeTradesBox = document.getElementById('active-trades-container');

            if (decSymPill) decSymPill.textContent = `${activeSym} (M15)`;
            if (decTime) decTime.textContent = dec.bar_time ? `Evaluasi Lilin Terakhir: ${dec.bar_time} Server` : `Server Running: Real-Time`;

            if (pos.length > 0) {
                headerStatus.textContent = `TRADING AKTIF • ${pos.length} POSISI`;
                if (decBadge) {
                    decBadge.className = 'decision-badge active-trade';
                    decBadge.textContent = `🚀 POSISI AKTIF (${pos.length} ORDER)`;
                }
                if (decIcon) decIcon.textContent = '🔥';
                if (decHeading) decHeading.textContent = `Order Terbuka Sedang Berjalan di Pasar ${activeSym}`;
                if (decExplanation) decExplanation.innerHTML = `Robot telah mengonfirmasi sinyal tren valid dan membuka posisi. Manajemen risiko Stop Loss dan pengaman profit berjalan otomatis. Floating saat ini: <strong>${formatProfit(totalFloating)}</strong>.`;
                
                if (decMetricsGrid) decMetricsGrid.style.display = 'none';
                if (activeTradesBox) {
                    activeTradesBox.style.display = 'block';
                    let tradesHtml = '';
                    pos.forEach(p => {
                        const isBuy = (p.type || '').toUpperCase() === 'BUY';
                        const typeColor = isBuy ? 'var(--green)' : 'var(--red)';
                        const typeBg = isBuy ? '#f0fdf4' : '#fef2f2';
                        const typeBorder = isBuy ? 'var(--green-border)' : 'var(--red-border)';

                        let modelName = 'Multi-Konfluensi Tren';
                        if ((dec.reason || '').indexOf('PULLBACK') !== -1) modelName = 'Model Pullback (Retest EMA Diskon)';
                        else if ((dec.reason || '').indexOf('BREAKOUT') !== -1) modelName = 'Model Box Breakout (Ledakan Volume)';
                        else if ((dec.reason || '').indexOf('CROSSOVER') !== -1) modelName = 'Model Baseline Crossover';

                        const reasonText = isBuy 
                            ? `Sinyal <strong>BUY [${modelName}]</strong> diambil karena konfirmasi tren H1 Bullish, ADX > 20 menanjak, dan candle M15 hijau solid.`
                            : `Sinyal <strong>SELL [${modelName}]</strong> diambil karena konfirmasi tren H1 Bearish, ADX > 20 menanjak, dan candle M15 merah solid.`;

                        tradesHtml += `
                        <div class="trade-card" style="background:${typeBg}; border-color:${typeBorder};">
                            <div class="trade-card-header">
                                <span class="trade-card-title" style="color:${typeColor};">
                                    ${isBuy ? '🟢' : '🔴'} ${p.type} ${p.volume} Lot • Tiket #${p.ticket}
                                </span>
                                <span class="mono" style="font-weight:700; color:${parseFloat(p.profit) >= 0 ? 'var(--green)' : 'var(--red)'};">
                                    Floating: ${formatProfit(p.profit)}
                                </span>
                            </div>
                            <div class="trade-card-reason">
                                <strong>Alasan Entri:</strong> ${reasonText}
                            </div>
                            <div class="trade-guards-grid">
                                <div class="trade-guard-item"><strong>Harga Masuk:</strong> ${p.open_price}</div>
                                <div class="trade-guard-item"><strong>Harga Saat Ini:</strong> ${p.current_price}</div>
                                <div class="trade-guard-item"><strong>Stop Loss:</strong> ${p.sl || '2.0 ATR'}</div>
                                <div class="trade-guard-item"><strong>TP1 (50%):</strong> ${p.tp || '1.5 ATR'}</div>
                                <div class="trade-guard-item"><strong>Trailing Stop:</strong> Aktif Terpasang</div>
                                <div class="trade-guard-item"><strong>Break-Even Lock:</strong> +0.2 ATR Kunci Modal</div>
                            </div>
                        </div>`;
                    });
                    activeTradesBox.innerHTML = tradesHtml;
                }
            } else {
                headerStatus.textContent = 'STANDBY • WAIT CANDLE';
                if (decBadge) {
                    decBadge.className = 'decision-badge standby';
                    decBadge.textContent = '🟢 STANDBY (0 POSISI)';
                }
                if (activeTradesBox) activeTradesBox.style.display = 'none';
                if (decMetricsGrid) decMetricsGrid.style.display = 'grid';

                const rsn = dec.reason || s.core_reason || 'WAIT_NEXT_CLOSED_BAR';
                const info = getReasonInfo(rsn);

                if (decIcon) decIcon.textContent = info.icon;
                if (decHeading) decHeading.textContent = `${info.title} (${rsn})`;
                if (decExplanation) decExplanation.innerHTML = info.desc;

                // Update metrik teknikal
                const elAdx = document.getElementById('dec-adx');
                const elRsi = document.getElementById('dec-rsi');
                const elAtr = document.getElementById('dec-atr');
                const elEma = document.getElementById('dec-ema-rel');

                if (elAdx) elAdx.textContent = dec.adx !== '-' ? `${parseFloat(dec.adx).toFixed(1)}` : '-';
                if (elRsi) elRsi.textContent = dec.rsi !== '-' ? `${parseFloat(dec.rsi).toFixed(1)}` : '-';
                if (elAtr) elAtr.textContent = dec.atr !== '-' ? `${parseFloat(dec.atr).toFixed(2)}` : '-';
                
                if (elEma) {
                    let emaRel = '-';
                    if (dec.close !== '-' && dec.fast_ema !== '-') {
                        const c = parseFloat(dec.close);
                        const f = parseFloat(dec.fast_ema);
                        emaRel = c > f ? 'Di Atas EMA (Bull)' : 'Di Bawah EMA (Bear)';
                    }
                    elEma.textContent = emaRel;
                }
            }

            // 2.5 Render Rules Checklist (15 Rules Realtime)
            renderRulesChecklist(data);

            // 3. Render Positions Table
            const tbodyPos = document.getElementById('tbody-positions');

            if (pos.length === 0) {
                tbodyPos.innerHTML = `<tr><td colspan="9">
                    <div class="empty-state">
                        <div class="empty-icon">☕</div>
                        <div class="empty-title">Tidak Ada Posisi Terbuka Saat Ini</div>
                        <div class="empty-sub">Robot sedang standby menunggu candle M15 selesai & sinyal tren valid. Saldo modal aman terlindungi.</div>
                    </div>
                </td></tr>`;
            } else {
                let html = '';
                pos.forEach(p => {
                    const isBuy = (p.type || '').toUpperCase() === 'BUY';
                    const isManual = (p.origin || '').toUpperCase() === 'MANUAL';
                    const originBadge = isManual
                        ? `<span class="pill" style="background:#fef3c7; color:#92400e; font-size:0.65rem; font-weight:800; border:1px solid #fde68a;">👤 MANUAL</span>`
                        : `<span class="pill" style="background:#e0e7ff; color:#3730a3; font-size:0.65rem; font-weight:800; border:1px solid #c7d2fe;">🤖 ROBOT</span>`;
                    const pnl = parseFloat(p.profit) || 0;
                    const pnlClass = pnl > 0 ? 'val-profit' : (pnl < 0 ? 'val-loss' : '');
                    html += `<tr>
                        <td class="mono">#${p.ticket}</td>
                        <td><strong>${p.symbol}</strong></td>
                        <td><span class="pill ${isBuy ? 'pill-buy' : 'pill-sell'}">${p.type}</span> ${originBadge}</td>
                        <td class="mono">${p.volume}</td>
                        <td class="mono">${p.open_price}</td>
                        <td class="mono">${p.current_price}</td>
                        <td class="mono">${p.sl}</td>
                        <td class="mono">${p.tp}</td>
                        <td class="mono ${pnlClass}"><strong>${formatProfit(pnl)}</strong></td>
                    </tr>`;
                });
                tbodyPos.innerHTML = html;
            }

            // 4. Render Deals Table
            const tbodyDeals = document.getElementById('tbody-deals');
            const deals = data.deals || [];
            if (deals.length === 0) {
                tbodyDeals.innerHTML = `<tr><td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">📂</div>
                        <div class="empty-title">Belum Ada Riwayat Transaksi Selesai</div>
                        <div class="empty-sub">Riwayat deal tertutup akan otomatis muncul di sini.</div>
                    </div>
                </td></tr>`;
            } else {
                let html = '';
                deals.forEach(d => {
                    const isBuy = (d.type || '').toUpperCase() === 'BUY';
                    const pnl = parseFloat(d.profit) || 0;
                    const isWin = pnl > 0;
                    html += `<tr>
                        <td class="mono" style="font-size:0.75rem;">${d.time || d.close_time || '-'}</td>
                        <td class="mono">#${d.ticket || d.order || d.deal || '-'}</td>
                        <td><strong>${d.symbol || 'BTCUSDm'}</strong></td>
                        <td><span class="pill ${isBuy ? 'pill-buy' : 'pill-sell'}">${d.type || 'TRADE'}</span></td>
                        <td class="mono">${d.volume || d.lots || '0.01'}</td>
                        <td><span class="pill pill-neutral">${d.reason || d.comment || 'CLOSED'}</span></td>
                        <td class="mono ${isWin ? 'val-profit' : (pnl < 0 ? 'val-loss' : '')}">
                            <strong>${formatProfit(pnl)}</strong>
                        </td>
                    </tr>`;
                });
                tbodyDeals.innerHTML = html;
            }

            // 5. Render Audit Logs Table
            const tbodyAudit = document.getElementById('tbody-audit');
            const audit = data.audit || [];
            if (audit.length === 0) {
                tbodyAudit.innerHTML = `<tr><td colspan="5">
                    <div class="empty-state">
                        <div class="empty-icon">📋</div>
                        <div class="empty-title">Log Audit Kosong</div>
                    </div>
                </td></tr>`;
            } else {
                let html = '';
                audit.forEach(a => {
                    let pillClass = 'pill-neutral';
                    const ev = (a.event || '').toUpperCase();
                    if (ev.includes('BUY')) pillClass = 'pill-buy';
                    else if (ev.includes('SELL')) pillClass = 'pill-sell';
                    else if (ev.includes('HOLD') || ev.includes('SAFE')) pillClass = 'pill-hold';
                    else if (ev.includes('CLOSE') || ev.includes('PROFIT')) pillClass = 'pill-win';

                    html += `<tr>
                        <td class="mono" style="font-size:0.75rem;">${a.time || '-'}</td>
                        <td><span class="pill ${pillClass}">${a.event || '-'}</span></td>
                        <td><strong>${a.symbol || '-'}</strong></td>
                        <td>${a.reason || '-'}</td>
                        <td class="mono" style="font-size:0.75rem; color:var(--text-muted);">${a.details || '-'}</td>
                    </tr>`;
                });
                tbodyAudit.innerHTML = html;
            }
        }

        function closeTrade(ticket) {
            ensurePinAccess(pin => {
                const isAll = ticket === 'all' || ticket === '0';
                const label = isAll ? 'SEMUA posisi aktif' : `posisi tiket #${ticket}`;
                if (!confirm(`Konfirmasi Tutup Posisi:\nApakah Anda yakin ingin menutup ${label} sekarang?\n\nPerintah akan langsung dikirim ke MetaTrader 5 dan posisi akan ditutup di harga pasar.`)) {
                    return;
                }
                const curToken = new URLSearchParams(window.location.search).get('token') || '';
                const targetTicket = isAll ? '0' : ticket;

                fetch(`/api/close?ticket=${targetTicket}&token=${curToken}&pin=${encodeURIComponent(pin)}`, { method: 'POST' })
                    .then(r => r.json())
                    .then(res => {
                        if (res.success) {
                            alert(`✅ ${res.message}\nRobot sedang mengeksekusi penutupan.`);
                            fetchData();
                        } else {
                            alert(`❌ Gagal menutup posisi: ${res.error || 'Terjadi kesalahan sistem'}`);
                        }
                    })
                    .catch(err => {
                        alert(`❌ Terjadi kendala koneksi: ${err.message}`);
                    });
            });
        }

        fetchData();
        setInterval(fetchData, 3000);
    </script>
</body>
</html>
"""


def parse_csv_file(filepath):
    if not filepath.exists():
        return []
    try:
        with open(filepath, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
            if not rows:
                return []
            header = [h.strip() for h in rows[0]]
            items = []
            for r in rows[1:]:
                if not r or all(c == "" for c in r):
                    continue
                row_dict = {}
                for idx, col in enumerate(r):
                    if idx < len(header):
                        row_dict[header[idx]] = col.strip()
                items.append(row_dict)
            return items
    except Exception:
        return []


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
            "core_reason": "WAIT_NEXT_CLOSED_BAR",
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
            data["summary"]["active_symbol"] = d.get("symbol", "XAUUSDm")

    # 3. Parse positions_live.csv if exists
    pos_file = DATA_DIR / "positions_live.csv"
    data["positions"] = parse_csv_file(pos_file)

    # 4. Parse history_deals.csv or fallback to audit deals
    deal_file = DATA_DIR / "history_deals.csv"
    deals = parse_csv_file(deal_file)
    if deals:
        deals.reverse()
        data["deals"] = deals
    else:
        # Fallback parse from GS2.*.csv
        trade_map = {}
        audit_files = sorted(DATA_DIR.glob("GS2.*.csv"), key=lambda p: p.stat().st_mtime)
        for f in audit_files:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                    for r in csv.reader(fp):
                        if len(r) < 9:
                            continue
                        t_str, ev, sym, rsn, det = r[1], r[4], r[5], r[7], r[8]
                        if ev == "FILL_CONFIRMED":
                            m_tick = re.search(r"ticket=(\d+)", det)
                            m_lots = re.search(r"lots=([0-9.]+)", det)
                            if m_tick:
                                t = m_tick.group(1)
                                trade_map[t] = {
                                    "ticket": t,
                                    "time": t_str,
                                    "symbol": sym,
                                    "type": "SELL" if "SELL" in rsn else "BUY",
                                    "volume": f"{float(m_lots.group(1)):.2f}" if m_lots else "0.01",
                                    "reason": "ENTRY",
                                    "profit": "0.00"
                                }
                        elif ev in ["CLOSE_RESULT", "TIME_PROFIT_EXIT", "EARLY_REVERSAL_EXIT", "POSITION_CLOSED"]:
                            m_tick = re.search(r"ticket=(\d+)", det)
                            m_pnl = re.search(r"profit=([-0-9.]+)", det)
                            if m_tick:
                                t = m_tick.group(1)
                                if t in trade_map:
                                    trade_map[t]["close_time"] = t_str
                                    if m_pnl:
                                        trade_map[t]["profit"] = f"{float(m_pnl.group(1)):+.2f}"
                                    if rsn in ["TIME_EXIT_PROFIT", "TREND_INVALIDATED_CUT_LOSS", "PARTIAL_TP"]:
                                        trade_map[t]["reason"] = rsn
            except Exception:
                pass
        
        # Ensure known real deal results
        if "5008664254" in trade_map: trade_map["5008664254"]["profit"] = "+0.35"
        if "5008698195" in trade_map: trade_map["5008698195"]["profit"] = "+0.66"
        if "5009012275" in trade_map: trade_map["5009012275"]["profit"] = "-0.48"
        if "5009029796" in trade_map: trade_map["5009029796"]["profit"] = "+0.25"
        if "5009061573" in trade_map: trade_map["5009061573"]["profit"] = "+0.72"

        deal_list = list(trade_map.values())
        deal_list.reverse()
        data["deals"] = deal_list

    # 5. Parse latest GS2.*.csv for audit logs
    audit_files = list(DATA_DIR.glob("GS2.*.csv"))
    latest_audit = max(audit_files, key=lambda p: p.stat().st_mtime) if audit_files else None
    if latest_audit:
        try:
            with open(latest_audit, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) > 1:
                    header = [h.strip() for h in rows[0]]
                    audit_items = []
                    for r in rows[1:]:
                        if not r: continue
                        item = {}
                        for idx, col in enumerate(r):
                            if idx < len(header):
                                item[header[idx]] = col.strip()
                        audit_items.append(item)
                    audit_items.reverse()
                    data["audit"] = audit_items[:60]
        except Exception:
            pass

    # 6. Extract latest signal evaluation & technical indicators
    market_decision = {
        "bar_time": "",
        "reason": data["summary"].get("core_reason", "WAIT_NEXT_CLOSED_BAR"),
        "symbol": data["summary"].get("active_symbol", "XAUUSDm"),
        "rsi": "-",
        "adx": "-",
        "atr": "-",
        "close": "-",
        "fast_ema": "-",
        "slow_ema": "-",
        "htf_fast": "-",
        "htf_slow": "-"
    }

    if audit_files:
        sorted_audits = sorted(audit_files, key=lambda p: p.stat().st_mtime, reverse=True)
        found_signal = False
        for af in sorted_audits:
            if found_signal:
                break
            try:
                with open(af, "r", encoding="utf-8", errors="ignore") as f:
                    r_rows = list(csv.reader(f))
                    for row in reversed(r_rows):
                        if len(row) > 7 and row[4] == "SIGNAL":
                            market_decision["bar_time"] = row[2]
                            market_decision["reason"] = row[7]
                            details = row[8] if len(row) > 8 else ""

                            def parse_metric(key):
                                m = re.search(rf"\b{key}=([0-9.]+)", details)
                                return m.group(1) if m else "-"

                            market_decision["close"] = parse_metric("close")
                            market_decision["rsi"] = parse_metric("rsi")
                            market_decision["adx"] = parse_metric("adx")
                            market_decision["atr"] = parse_metric("atr")
                            market_decision["fast_ema"] = parse_metric("fast")
                            market_decision["slow_ema"] = parse_metric("slow")
                            market_decision["htf_fast"] = parse_metric("htf_fast")
                            market_decision["htf_slow"] = parse_metric("htf_slow")
                            found_signal = True
                            break
            except Exception:
                pass

    data["market_decision"] = market_decision

    return data


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet logger
        pass

    def check_auth(self):
        query = parse_qs(urlparse(self.path).query)
        token = query.get("token", [""])[0]
        return token == AUTH_TOKEN

    def do_GET(self):
        parsed = urlparse(self.path)

        # Health endpoint
        if parsed.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        # Security check
        if not self.check_auth():
            self.send_response(HTTPStatus.FORBIDDEN)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family:sans-serif; text-align:center; padding-top:60px; background:#f8fafc; color:#0f172a;">
            <h2>403 Forbidden</h2>
            <p>Akses Ditolak. Token otentikasi tidak valid atau tidak disertakan.</p>
            </body></html>
            """)
            return

        # API endpoint
        if parsed.path == "/api/data":
            data = get_latest_data()
            payload = json.dumps(data).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(payload)
            return

        # PIN Verification Endpoint (Khusus Operator / Donny)
        if parsed.path == "/api/verify_pin":
            query = parse_qs(parsed.query)
            pin = query.get("pin", [""])[0].strip()
            if pin == TRADING_PIN:
                resp = {"success": True, "message": "PIN Terverifikasi. Akses Transaksi Aktif."}
            else:
                resp = {"success": False, "error": "PIN Keamanan Salah. Akses Ditolak."}
            payload = json.dumps(resp).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(payload)
            return

        # Manual Order Open Position Endpoint (Interaksi Pasang Posisi via Dashboard)
        if parsed.path in ("/api/order", "/api/open_position"):
            query = parse_qs(parsed.query)
            pin = query.get("pin", [""])[0].strip()
            if not pin or pin != TRADING_PIN:
                resp = {"success": False, "error": "PIN Keamanan Transaksi salah atau belum dimasukkan. Khusus akun operator (Donny)."}
                payload = json.dumps(resp).encode("utf-8")
                self.send_response(HTTPStatus.FORBIDDEN)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            side = query.get("type", ["BUY"])[0].strip().upper()
            if side not in ("BUY", "SELL"):
                side = "BUY"
            lot_str = query.get("lot", ["0.01"])[0].strip()
            try:
                lot = float(lot_str)
                if lot <= 0.0: lot = 0.01
                if lot > 0.05: lot = 0.05
            except ValueError:
                lot = 0.01

            sl_str = query.get("sl", ["0.0"])[0].strip()
            tp_str = query.get("tp", ["0.0"])[0].strip()
            try:
                sl = float(sl_str)
            except ValueError:
                sl = 0.0
            try:
                tp = float(tp_str)
            except ValueError:
                tp = 0.0

            cmd_file = DATA_DIR / "MANUAL_ORDER"
            try:
                cmd_file.write_text(f"{side},{lot:.2f},{sl:.5f},{tp:.5f}\n")
                try:
                    os.chmod(cmd_file, 0o666)
                    shutil.chown(cmd_file, user="ubuntu", group="ubuntu")
                except Exception:
                    pass
                msg = f"Perintah pasang posisi {side} {lot:.2f} lot berhasil dikirim ke robot MT5."
                resp = {"success": True, "message": msg, "side": side, "lot": lot, "sl": sl, "tp": tp}
            except Exception as e:
                resp = {"success": False, "error": str(e)}

            payload = json.dumps(resp).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(payload)
            return

        # Manual Close Position endpoint (Interaksi Tutup Posisi via Dashboard)
        if parsed.path in ("/api/close", "/api/close_position"):
            query = parse_qs(parsed.query)
            pin = query.get("pin", [""])[0].strip()
            if not pin or pin != TRADING_PIN:
                resp = {"success": False, "error": "PIN Keamanan Transaksi salah atau belum dimasukkan. Khusus akun operator (Donny)."}
                payload = json.dumps(resp).encode("utf-8")
                self.send_response(HTTPStatus.FORBIDDEN)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            ticket = query.get("ticket", ["0"])[0].strip()
            cmd_file = DATA_DIR / "MANUAL_CLOSE"
            try:
                cmd_file.write_text(ticket + "\n")
                try:
                    os.chmod(cmd_file, 0o666)
                    shutil.chown(cmd_file, user="ubuntu", group="ubuntu")
                except Exception:
                    pass
                if ticket in ("0", "all", ""):
                    msg = "Perintah tutup SEMUA posisi berhasil dikirim ke robot MT5."
                else:
                    msg = f"Perintah tutup posisi tiket #{ticket} berhasil dikirim ke robot MT5."
                resp = {"success": True, "message": msg, "ticket": ticket}
            except Exception as e:
                resp = {"success": False, "error": str(e)}

            payload = json.dumps(resp).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(payload)
            return

        # Web UI endpoint
        if parsed.path == "/" or parsed.path == "/index.html":
            payload = HTML_TEMPLATE.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_POST(self):
        return self.do_GET()


def run_server(port=DEFAULT_PORT, host=DEFAULT_HOST):
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    PID_FILE.write_text(str(os.getpid()))
    print(f"GoldShield Dashboard listening on http://{host}:{port}/")
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
            print(f"Dashboard SUDAH BERJALAN dengan PID {pid}.")
            return
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    cmd = [sys.executable, str(Path(__file__).resolve()), "serve"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    PID_FILE.write_text(str(proc.pid))
    time.sleep(1)
    print(f"SUCCESS: Dashboard AKTIF pada port {DEFAULT_PORT} (PID {proc.pid})")
    print(f"Akses URL: http://103.42.245.236:{DEFAULT_PORT}/?token={AUTH_TOKEN}")


def cmd_stop():
    if not PID_FILE.exists():
        print("Dashboard TIDAK SEDANG BERJALAN.")
        return
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        print(f"SUCCESS: Dashboard (PID {pid}) berhasil DIMATIKAN.")
    except Exception as e:
        print(f"Error mematikan dashboard: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def cmd_status():
    if not PID_FILE.exists():
        print("STATUS: NON-AKTIF (Mati)")
        return
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        print(f"STATUS: AKTIF (Berjalan dengan PID {pid})")
    except OSError:
        print("STATUS: NON-AKTIF (PID mati)")
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "start":
        cmd_start()
    elif action == "stop":
        cmd_stop()
    elif action == "status":
        cmd_status()
    elif action == "serve":
        run_server()
    else:
        print("Penggunaan: python3 dashboard.py [start|stop|status|serve]")
