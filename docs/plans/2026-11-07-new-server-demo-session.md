# New server DEMO20 session implementation plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Create and activate a genuinely new, explicitly authorized DEMO-only server session without importing or fabricating PC state and without weakening existing trading controls.

**Architecture:** Keep the original migration runtime and EA binary unchanged. A separate fresh-server launcher prepares a new Magic/preset/namespace, lets the stock EA initialize real persistent state with trading disabled, verifies that state using a read-only native report, then permits run mode only with a verified-stage receipt and explicit activation marker. Never generate MT5 variables, locks or an import receipt in Python.

**Tech stack:** Python stdlib, unittest, existing compiled MQL5 DEMO20 EA, small read-only MQL5 script, Wine, user systemd, existing read-only Telegram notifier.

## Scope and authorization

- User explicitly selected a NEW session and confirmed PC EA disabled. Raw runtime context verified Telegram owner1227557858, group-1003987695448, topic17167. This is not authorization for real accounts, new algorithms, forced orders, higher risk or resetting existing sessions.
- Preserve the original presets, binary, migration launcher, real/Cent files and any pre-existing state. Use a newly generated positive Magic different from the packaged PC Magic and a new empty session directory.
- Preserve all risk and indicator inputs from the pinned stock preset except new Magic and deliberate stage/run opt-in flags. Target Exness-MT5Trial7, USD, DEMO, hedging, XAUUSDm M15, max0.01lot, oneposition,3entries/day,20 submissions. Failed submissions still consume slots.
- Original source already supports clean initialization: GSStorage::Init creates the new account/symbol/Magic namespace, and GSDemo20Init seeds its counter from matching broker history. Existing lock plus missing globals fails closed; never remove these.

## Task1: Implement separate fresh-session preparation with TDD

**Files:** create `tools/new_server_session.py`, `tests/test_new_server_session.py`.

1. Write a failing test for preparing a new empty session directory: preserve base risk values, generate unique/new Magic, make STAGE opt-ins false and RUN opt-ins true, no import receipt and no gvariables/locks generated. Observe RED, implement minimal helper, observe GREEN.
2. Test overwrite refusal, malformed/old Magic, wrong packaged hash and unsafe flags; implement validation with no deletions or automatic reset.
3. Expose CLI `prepare --session-dir DIR --terminal-dir DIR [--magic N]`, `verify-stage --session-dir DIR`, and `launch --session-dir DIR --mode stage|run`. Pure helper functions must be independently testable; use explicit immutable file hashes and private metadata. Do not expose account login or credentials on stdout.
4. Stage/run presets live in a new `MQL5/Presets/GoldShieldServer/<session-name>/` directory. Use source binary only after matching bundle-manifest hash. Terminal source of account credentials remains its own saved private store; no Password in new files.
5. STAGE config sets Experts Enabled0, AllowLiveTrading0, AllowDllImport0, and loads stock GoldShield_DEMO20 with stage preset. It also launches the read-only preflight script below with nonce and new Magic via ScriptParameters. RUN config sets trading flags1 and uses active preset. Script may also be included for a post-start read-only report; always ShutdownTerminal0.

## Task2: Native read-only preflight report and real-stage verification

**Files:** create `tools/mql5/GoldShield_ServerPreflight.mq5`; extend above tests.

1. Test report rejection for REAL/CONTEST, wrong broker/currency/symbol/account, disconnected, non-hedging, nonpositive/nonfinite equity/reference, open account positions/pending orders, missing/stale/wrong-nonce report, invalid counter/limit/schema/block/pending, missing genuine marker/global file, ERROR_BLOCKED/risk/history-unavailable snapshot. Observe RED per behavior before implementation.
2. Native script inputs `ProbeMagic`, `RequestId`, `WaitForState` (or documented equivalent). Compute the stock account/server/symbol/Magic GS2 key exactly. Use only AccountInfo, TerminalInfo, PositionsTotal, OrdersTotal, SymbolInfo and GlobalVariableGet/Check. No trading requests, DLL/network, GlobalVariableSet or account credentials.
3. Wait boundedly for connection and, for stage verification, stock global schemas. Write one CSV row under MQL5/Files/GoldShield with nonce, connected, DEMO mode, hedging mode, server, currency, login, symbol, balance/equity, account positions/orders, broker trade/expert permission, terminal trade permission, Magic, audit_key, storage schema/reference, trial schema/used/limit, blocked and pending. FileFlush/FileClose. The private account number is for binding; never print it to chat.
4. Verify nonce + host-file freshness and exactly one report row, genuine `.lock`, nonempty bases/gvariables.dat and actual `demo20_<Magic>.csv`. Initial used must be0, limit20, trial/storage schema1, positive reference, flat account, no hard error. The EA, not Python, creates these values. Require matching account/prefix and snapshot consistency.
5. Write a true `stage-verified.json` labelled FRESH_SERVER_DEMO20, not an import receipt. Bind actual account identity, Magic, prefix and generated file hashes. RUN also requires `ACTIVATE_SERVER_DEMO20` and persistent marker/globals. On subsequent runs do not require positions flat or snapshot counter0; allow management of the last position/cap and let stock safeguards handle persistent block/risk state. Never auto-prepare another session after a failure.

## Task3: Validate command construction and deployment templates

**Files:** new `deployment/server-demo/goldshield-server-demo.service`, `docs/NEW_SERVER_DEMO_SESSION.md`.

- Build Wine argv with `winepath -w`, `/portable`, fixed config selected by mode; refuse a concurrent terminal64.exe for ubuntu before launch; execute without shell. Validate all immutable hashes before stage/run. Require explicit prepared session for stage and verified receipt + activation marker for run.
- User service uses Requires/After desktop, Conflicts old setup/active services, no broad host restarts, WINEPREFIX/DISPLAY explicit, same resource caps as bootstrap, Restart bounded. Production session directory supplied explicitly by environment or generated drop-in; no broker secrets.
- Document fresh vs migration semantics, manual activation, no forced test order, restart preserves same Magic/state, notifier baseline before activation, and that market/risk filters can legitimately produce zero trades.
- Run focused and full Python tests; compile native probe with actual MetaEditor/Wine and require0errors/0warnings. Stock source/binary/presets hash unchanged. Graphify refresh/query, diff check, static security scan and independent spec then quality review before commit/push.

## Task3b: Isolate startup charts without touching persistent EA state

Official startup behavior opens an additional chart when Symbol is supplied. Restoring a saved STAGE profile and also loading RUN on a new chart can retain a disabled EA or collide with the exclusive same-namespace lock. Prevent this with a session-owned chart profile, not by deleting EA state.

- TDD: generate `[Charts] ProfileLast=<session-owned-name>` in all new configs. Add `configure-profile --session-dir DIR` to upgrade an already prepared but not verified/activated session, preserving Magic, nonce, presets and terminal globals/locks; reseal only changed config hashes/private metadata. Reject post-verification reconfiguration.
- Before CLI launch, after checking no same-user terminal process and all receipt/hash guards, archive only this session-owned profile directory to private session/profile-backups and recreate it empty. Do not mutate other chart profiles, gvariables, broker login stores, audit, locks, counters or reference. Use strict resolved path containment and reject symlinks/non-directories.
- Keep argv construction pure. A separate reset/prepare-owned-profile operation is called only by the executable CLI just before exec; test archive/recreate, other profiles/state byte preservation, unsafe paths, symlinks and verification gate. A Wine restart then attaches exactly the one sealed EA preset to a clean UI profile while resuming genuine persistent state.
- Parent must validate actual native profiles location/casing and perform one real no-order restart acceptance test after activation.

## Task4: Parent-only live verification and activation

1. Verify raw platform IDs and target host (already read), current native target account and no previous server import/activation.
2. Gracefully close setup MT5 (Restart=on-failure), wait boundedly for exit, stop only completed setup unit; do not restart desktop/host or change account files. Back up terminal config/state privately.
3. Deploy compiled read-only script. Prepare new session as ubuntu using verified helpers. First run script-only preflight with Experts Enabled0/AllowLiveTrading0, no EA attached and WaitForState=false: verify actual DEMO/account/connection/permissions/flat and unused namespace (and matching history if available). Then run STAGE, which is explicitly no-order initialization, NOT state-free/read-only: the attached stock EA naturally creates namespace/counter/reference and can consume candle markers. Verify real native state/report/snapshot; retain failures for diagnosis rather than erase/recreate state.
4. Configure existing Telegram observer's condition to the real fresh stage receipt, not an invented migration receipt. Confirm exact destination and baseline actual stage history before activation. No repeated synthetic trade/service messages.
5. Create the explicit activation marker for the authorized new session only after all gates; start/enable the new service. Verify actual post-start broker connection/permissions, EA snapshot/audit, unchanged counter/reference, symbol/timeframe and notifier activity. Do not force an order to prove activity. A Saturday stale quote is not a reason to weaken a guard.
6. Record actual verified evidence and residual limits, commit/push code (no state/logins/reports/private account IDs), verify remote HEAD. Report live state honestly; if broker credentials/permissions fail, ask the operator and leave trading disabled.
