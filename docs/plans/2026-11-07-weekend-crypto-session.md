# Weekend Crypto (BTCUSDm) Session Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Provide an isolated weekend crypto trading session (`BTCUSDm` M15) on the server for Donny's demo account (`Exness-MT5Trial7`), maintaining separate state/counter from the Gold session (`XAUUSDm`) and allowing clean operational switching between weekend and weekday modes.

**Architecture:**
- Existing Gold session (`/home/ubuntu/goldshield-server-demo/server-20261107`) remains preserved and untouched.
- Native probe `GoldShield_ServerPreflight.mq5` generalized to support `_Symbol` dynamically instead of hardcoded `XAUUSDm`.
- Session orchestrator `tools/new_server_session.py` parameterized to support `--symbol` (default `XAUUSDm`, optional `BTCUSDm`) and custom base preset.
- Crypto-tailored preset `deployment/linux-guide/presets/DEMO20_BTCUSDm.set` with safe crypto spread (`5000` points) and slippage deviation buffer (`300` points), keeping strict risk caps (`0.01` lot, 1 position, max 3 entries/day, max 20 trial submissions).
- Clean systemd session switching between weekend mode and weekday mode.

**Tech Stack:** MQL5, Python 3 stdlib, MetaEditor 64 (Wine), systemd user unit, git.

---

### Task 1: Generalize MQL5 Server Preflight Probe to Support Any Chart Symbol

**Objective:** Update `tools/mql5/GoldShield_ServerPreflight.mq5` so that the audit key identity and history deal filtering use `_Symbol` instead of hardcoded `"XAUUSDm"`. Compile with MetaEditor and verify 0 errors, 0 warnings.

**Files:**
- Modify: `tools/mql5/GoldShield_ServerPreflight.mq5:9,47`
- Output: `tools/mql5/GoldShield_ServerPreflight.ex5`
- Target: `/home/ubuntu/.mt5/drive_c/Program Files/MetaTrader 5/MQL5/Scripts/GoldShield_ServerPreflight.ex5`

**Verification:** Compile with Wine MetaEditor64.exe; verify log output has `0 errors, 0 warnings`.

---

### Task 2: Parameterize Session Helper for Dynamic Symbol and Preset

**Objective:** Update `tools/new_server_session.py` to support `--symbol` (defaults to `XAUUSDm`) and `--base-preset` (defaults to `DEMO20_CURRENT.set`), making `audit_key`, `PREFLIGHT.ini`, `STAGE.ini`, `RUN.ini`, and stage verification symbol-aware.

**Files:**
- Modify: `tools/new_server_session.py`
- Modify: `tests/test_new_server_session.py`

**Verification:** Run `/home/ubuntu/goldshield-linux/test-venv/bin/python -m unittest discover -s tests -v`. All tests pass.

---

### Task 3: Create Tested BTCUSDm Preset and Update Bundle Manifest

**Objective:** Create `deployment/linux-guide/presets/DEMO20_BTCUSDm.set` with verified crypto execution parameters (lot 0.01, spread 5000, deviation 300, 3 entries/day, 20 trial limit), and update `deployment/linux-guide/bundle-manifest.json`.

**Files:**
- Create: `deployment/linux-guide/presets/DEMO20_BTCUSDm.set`
- Modify: `deployment/linux-guide/bundle-manifest.json`

**Verification:** Manifest hash check passes.

---

### Task 4: Prepare, Stage, and Verify Weekend BTCUSDm Session

**Objective:** Bootstrap `/home/ubuntu/goldshield-server-demo/weekend-btc-20261107` with a fresh unique Magic Number, run STAGE under terminal, verify native report, flat positions, and unblocked ready state.

**Files:**
- Create session: `/home/ubuntu/goldshield-server-demo/weekend-btc-20261107`
- Native verification: `stage-verified.json`

**Verification:** `stage-verified.json` generated with status `FRESH_SERVER_DEMO20_STAGE_VERIFIED` for symbol `BTCUSDm`.

---

### Task 5: Implement Operational Weekend/Weekday Switcher

**Objective:** Provide a tested switcher script `tools/switch_trading_mode.py` and systemd drop-in support to cleanly stop the active session, switch between Gold Mode and Weekend Crypto Mode, and restart the service without state corruption.

**Files:**
- Create: `tools/switch_trading_mode.py`
- Documentation: `docs/WEEKEND_CRYPTO_TRADING.md`

**Verification:** Dry-run and live toggle verified.

---

### Task 6: Activate Weekend Crypto Session and Live Verification

**Objective:** Activate the weekend BTC session, launch MT5, verify native trading is ON (`terminal_trade_allowed=1`), Allow Algo Trading is checked, and notifier tracks the new session.

**Verification:** Live telemetry inspection and Telegram notifier confirmation.

---

### Task 7: Git Commit and Push

**Objective:** Commit all verified changes and push to `origin/main`. Clean working tree.
