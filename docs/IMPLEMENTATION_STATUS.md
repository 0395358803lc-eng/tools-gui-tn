# Implementation Status — P0 → P3

Branch: `fix/harden-whatsapp-automation`  
Base: `main`  
Updated: 20/08/2026

Legend:

- ✅ Implemented in code + regression/unit tests added where practical.
- ⚠️ Implemented/configured but still requires real Windows/AVD/WhatsApp verification before release.

## P0 — Correctness & safety

| Item | Status | Notes |
|---|---|---|
| Remove tracked build/dist/log/cache/user settings | ✅ | Generated/runtime files removed from Git tracking and ignored. |
| Bundle only default config | ✅ | PyInstaller no longer bundles user `settings.json`. |
| Explicit ADB command result/errors | ✅ | Distinguishes not-found, timeout, exit code and stderr/stdout. |
| Safe text input | ✅ | User text passed as arguments; no apostrophe deletion/custom partial escaping. |
| Multi-image correctness | ✅ | Images sent sequentially; log count matches actual completed sends. |
| Prevent duplicate retry after partial media send | ✅ | `PartialSendError` is non-retryable at recipient workflow level. |
| Explicit settings initialization | ✅ | No filesystem side effect on module import; startup handles config error. |
| P0 runtime checkpoint | ⚠️ | Needs real pytest/Windows build/AVD smoke evidence before release. |

## P1 — Reliability

| Item | Status | Notes |
|---|---|---|
| Prioritized selector strategy | ✅ | resource-id → semantic desc/hint/text → heuristic. |
| Remove fixed Phone coordinate | ✅ | Fails safely instead of tapping an unverified coordinate. |
| WhatsApp state detection | ✅ | HOME/PICKER/FORM/CONVERSATION/OTHER/UNKNOWN. |
| Conservative state-aware navigation | ✅ | Skips restart/New Chat only when current state is safely known. |
| Retry backoff | ✅ | Delay increases by attempt. |
| Circuit breaker | ✅ | Stops after configurable consecutive recipient failures. |
| Minimum pacing | ✅ | Core enforces minimum delay even if legacy config uses zero. |
| Cancellation propagation | ✅ | Worker → bot/controllers → UI waits → activity waits. |
| Diagnostic masking | ✅ | Phone values masked in operational logs/errors. |
| Worker/Bot/media regression tests | ✅ | Retry, partial, cancellation, pacing, selectors and routing covered. |
| Windows CI + Ruff | ⚠️ | Workflow configured; current connector has not provided a green run/check result. |

## P2 — Maintainability / packaging

| Item | Status | Notes |
|---|---|---|
| User-data runtime paths | ✅ | Windows defaults to `%LOCALAPPDATA%\ToolsGuiTinWhatsApp`. |
| Legacy settings migration | ✅ | Copies valid legacy JSON once; does not delete source or overwrite new settings. |
| Logs outside install directory | ✅ | Stored in user-data. |
| Dependency source of truth | ✅ | `pyproject.toml`; extras split into `dev` and `build`. |
| PyInstaller hardening | ✅ | Clean build, user config excluded, UPX disabled by default. |
| Packaged EXE self-test in CI | ⚠️ | Configured; green workflow evidence still required. |
| README | ✅ | Installation, Android/ADB, run/test/build, troubleshooting and data paths documented. |
| Compatibility baseline | ✅ | Historical baseline separated from current-version certification. |
| Report privacy documentation | ✅ | Logs masked; CSV/XLSX operational reports contain full phone values. |

## P3 — Optimization / operational tooling

| Item | Status | Notes |
|---|---|---|
| Contact resolution strategy | ✅ | Dedicated resolver + in-memory per-worker/device cache. |
| Contact cache | ✅ | Marked only after UI detection/save/open-chat success; not persisted across runs. |
| Session reuse | ✅ | Best-effort Back navigation after success; unknown state falls back to restart workflow. |
| Device preflight | ✅ | ADB, online, boot, WhatsApp package and UI dump checks. |
| Broadcast input preflight | ✅ | Phone/content/image/interval validation; duplicate phone warning. |
| Unicode readiness warning | ✅ | ADBKeyboard absence is warning when non-ASCII message detected. |
| Structured recipient results | ✅ | success/failed/partial/cancelled + attempts/elapsed/error. |
| Automatic CSV/XLSX report export | ✅ | Stored in user-data `reports/`; formula injection neutralized. |
| Report export side-effect isolation in tests | ✅ | Core tests monkeypatch worker exporters. |
| Stored UI selector fixtures | ✅ | Home, contact form and conversation XML fixtures. |
| Optional emulator integration smoke suite | ✅ | Runs only with `WA_INTEGRATION_SERIAL`; does not send real messages. |
| Full real-device end-to-end validation | ⚠️ | Requires a selected AVD and current WhatsApp build; not proven by connector-only source review. |

## Release gate

Do not merge/release solely because the implementation table is green. Before release, require all of the following on the exact target commit:

1. Windows CI workflow passes Ruff + pytest.
2. `python -m app --self-test` passes.
3. PyInstaller build succeeds and packaged EXE `--self-test` passes.
4. Opt-in emulator smoke test passes on the target AVD.
5. Selector compatibility is rechecked against the installed WhatsApp version.
6. One controlled text send succeeds.
7. One controlled media send succeeds.
8. Stop/cancellation behavior is manually exercised once.
9. Generated report is checked for correct success/failure/partial status and expected privacy properties.

## Merge policy

All changes currently belong on the feature branch. `main` should remain unchanged until review/validation is complete and merge is explicitly authorized.
