# NEW server DEMO20 session (separate from PC migration)

This helper creates a **FRESH_SERVER_DEMO20**, not an imported PC session.
Original migration scripts, strategy, stock EX5 and base presets are unchanged.
Owner authorization: 1227557858 in chat -1003987695448, thread 17167; PC EA disabled.
A new positive random Magic (at most 2^53-1, different from the old Magic) naturally
uses a separate account/server/symbol/Magic namespace. No fabricated counters,
GlobalVariables, locks, state-import receipts, credentials or passwords are written.

## CLI

Run as the intended unprivileged terminal owner, with explicit terminal/session paths:

```text
python3 tools/new_server_session.py prepare --session-dir DIR --terminal-dir DIR [--magic N]
python3 tools/new_server_session.py bind-preflight --session-dir DIR --report SAVED_NATIVE_PREFLIGHT.csv
python3 tools/new_server_session.py launch --session-dir DIR --mode stage
python3 tools/new_server_session.py verify-stage --session-dir DIR
python3 tools/new_server_session.py launch --session-dir DIR --mode run
```

`--magic` is primarily for reproducible fixtures; never reuse an earlier namespace.
Prepare is single-use: it refuses existing session/preset directories, source hash
mismatches, unsafe base flags, old Magic and modified installed Expert binary.
It writes private session metadata and isolated presets under
`MQL5/Presets/GoldShieldServer/<safe-session-name>/`. The base risk fields are
preserved byte-value-for-value except MagicNumber and the two explicit opt-ins.
Generated config/preset/Expert hashes are pinned; tampering blocks launch.
No automatic retry/reset/reprepare is permitted after failed guards.

## Session-owned chart profiles

New sessions pin `[Charts] ProfileLast=GS_Server_<session-name>_<nonce-first8>` in
PREFLIGHT, STAGE and RUN. Existing **unverified, nonactivated** prepared sessions
can be upgraded without changing Magic, nonce, presets or any terminal state:

```text
python3 tools/new_server_session.py configure-profile --session-dir DIR
```

Upgrade validates every existing hash first, rejects any stage receipt or activation
marker and any same-user terminal process, then atomically replaces each private
config and finally reseals private metadata. An interrupted upgrade fails closed
on hash mismatch; never reset EA state or fabricate a receipt to repair it.

The CLI launcher validates all launch guards (including no same-user terminal)
before archiving **only this session's profile directory** into private
`DIR/profile-backups/<profile-name>-<unique-suffix>` and recreating it empty, mode
0700. `launch_argv` remains pure. Existing case-insensitive MQL5/Profiles/Charts
casing is respected; ambiguous roots, symlinks, non-directories and paths outside
the exact owned profile are rejected. Other profiles, broker Config, native globals,
locks, counters, reference and audit files are never removed or reset. Restart
attaches the stock EA once to an empty UI profile and resumes its existing native
state using the unchanged sealed active Magic/preset. Profile backups are archives,
not imported EA state. These are local trusted-user path guarantees, not
cryptographic attestation against a user able to rewrite all local evidence.

Where generated configs contain `[Common]`, `KeepPrivate=1` explicitly retains
the terminal's existing cached connection credentials; no password is read or written.
Native profile selection/restart behavior remains a mandatory parent check.

## Operator gates (not executed by this change)

1. Independently compile `tools/mql5/GoldShield_ServerPreflight.mq5` using actual
   MetaEditor; install EX5 under `MQL5/Scripts/GoldShield_ServerPreflight.ex5`.
   Parent owns compile, installation and all live operations. This patch's tests
   are filesystem fixtures, not proof of native compilation or broker behavior.
2. First perform script-only diagnostic using generated `PREFLIGHT.ini` and
   `preflight-probe.set` (`WaitForState=false`, Experts disabled, live trading OFF).
   Parent must check real DEMO connection/flatness and unused new namespace/history
   before any EA initialization. This diagnostic is not a stage receipt.
3. After the script-only preflight passes, preserve its private CSV and use
   `bind-preflight --session-dir DIR --report SAVED_NATIVE_PREFLIGHT.csv`. This
   selects the validated account in Common Login/Server/KeepPrivate for all
   configurations without reading its password. Alternative config files with
   no Login can start unauthenticated despite a saved account database. Binding
   is routing selection, not current authorization: retained evidence is accepted
   for selection, but STAGE still needs a new <=120-second native report and must
   match the selected account. Verified/activated sessions, mismatched evidence,
   existing namespaces and changed pins reject binding. Common sections are
   replaced, not duplicated; persistent EA state is never modified.
4. `launch ... --mode stage` is **no-order initialization**, not read-only: the
   stock attached EA creates its own persistent state and may consume a candle
   marker. Both preset opt-ins are false; Experts Enabled=0 and AllowLiveTrading=0
   keep the native terminal trading flag OFF as well. The attached EA still
   initializes and observes state. Enabled=1 alone can enable the global terminal
   trading flag even when AllowLiveTrading=0, so do not conflate those settings.
   Only the separate native probe is read-only. Experts Account=1/Profile=1 latch
   auto-trading OFF on account/profile change in both STAGE and RUN.
4. `verify-stage` requires a single fresh (<=120s) native CSV row with the exact
   nonce, live DEMO/Exness-MT5Trial7/USD/hedging/XAUUSDm identity and broker permissions,
   terminal automated-trading permission explicitly OFF (0) during STAGE,
   positive finite balance/equity/reference, zero account positions/orders,
   correct double-hash GS2 prefix, schema=1/trial_schema=1, used=0, limit=20,
   blocked=0/pending=0. Native nonempty `.lock` and persistent `Bases/gvariables.dat`
   (Bases case-insensitive) plus genuine `demo20_<magic>.csv` must exist and agree.
   ERROR_BLOCKED, PAUSED_RISK and unavailable history reject verification.
5. Verification finalizes RUN `[Common] Login`/Server with actual native identity,
   then seals config/preset/binary hashes and private `stage-verified.json` with
   status `FRESH_SERVER_DEMO20_STAGE_VERIFIED`. Login/financial values are not
   printed. This is a local evidence receipt, not cryptographic broker attestation;
   a user able to rewrite all local evidence remains inside the trust boundary.
6. Independently review the evidence. Only explicitly authorized operator writes
   `ACTIVATE_SERVER_DEMO20` containing the session nonce. Helper never creates it.
   Run requires the receipt, matching nonce, unchanged immutable hashes, and the
   same persistent state paths/inodes. Persistent contents are deliberately not
   hash-frozen: counters/reference management must survive normal EA updates.
   Restarts do **not** require fresh probe, used=0 or flat positions, so the last
   position remains managed after the 20-submission cap. Never delete state to
   repair a failing guard. Native EA remains the counter and risk authority.

The launcher rejects another same-user terminal64 process, invokes
`winepath -w CONFIG`, and execs argument-list `wine TERMINAL /portable /config:...`
with `os.execvpe`, never a shell. The new user-service template requires the desktop,
conflicts with old setup/active units, caps resources and bounds restarts. Supply
`GOLDSHIELD_SESSION_DIR` explicitly in an operator drop-in; no service is installed
or started by this patch. No host restart is authorized.

## Native CSV contract

`MQL5/Files/GoldShield/server_preflight.csv`, comma-separated, one header and one row:

```text
nonce,connected,account_mode,margin_mode,server,currency,login,symbol,balance,equity,positions_total,orders_total,account_trade_allowed,account_expert_allowed,terminal_trade_allowed,magic,audit_key,store_schema,reference,trial_schema,entry_submissions,limit,blocked,pending,history_available,matching_history_deals,namespace_present
```

Enums are native `ACCOUNT_TRADE_MODE_DEMO` and
`ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`, not fabricated labels. Probe inputs:
`ProbeMagic`, `RequestId`, `WaitForState` (default true). Wait is bounded at 60s for
connection and optional existing schemas. Missing state is reported as EMPTY_VALUE,
never created. GSStorage key is exactly `GS2.%08X%08X` for FNV32/DJB-XOR32 of UTF-16
code units in `server|login|XAUUSDm|magic`. It reads account/terminal permissions,
position/order totals and existing GlobalVariables only, then flushes/closes its
own CSV and prints a nonsecret saved acknowledgement. Never share CSV/metadata
publicly: these contain private account identity and financial values.

## Verification

```text
/home/ubuntu/goldshield-linux/test-venv/bin/python -m unittest discover -s tests -v
```

Fixture coverage includes isolated prepare, guards, native evidence verification,
wrong identity/nonce/stale/nonfinite/nonflat/blocked cases, missing native state,
run activation/receipt/hash gates, resume at used=20 with an open position, and
source-only read-only probe/service contracts. Native compilation and actual
terminal initialization remain separate mandatory parent checks before deployment.
