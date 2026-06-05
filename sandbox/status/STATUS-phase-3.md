Status: DONE

Phase 3 delivers the sandbox lifecycle layer: `SandboxManager` on the HA
Core side owns a `dict[str, SandboxProcess]` keyed by group name and
spawns each group lazily through `ensure_started`. Each `SandboxProcess`
runs an asyncio supervisor task that launches
`python -m hass_client.sandbox_v2 --group … --url … --token …`, reads
stdout for the `sandbox_v2:ready` marker, and watches the process for
unexpected exits. Restart-on-crash is bounded to 3 attempts in a 60s
sliding window with a small backoff sleep between attempts; exceeding
the budget transitions the sandbox to `failed` and `ensure_started`
raises `SandboxFailedError` so Phase 4 callers can push affected
entries to `setup_retry`. The client-side `SandboxRuntime` is the
Phase 3 stub described in the prompt — it parses CLI args, prints the
ready marker on stdout, and waits for SIGTERM/SIGINT (or an in-process
`request_shutdown()` call) before returning 0. The runtime is launched
as a real subprocess; the Phase 4 websocket transport is the next
piece to plug in.

Files added:
- `homeassistant/components/sandbox_v2/manager.py`
- `sandbox_v2/hass_client/hass_client/sandbox.py`
- `sandbox_v2/hass_client/hass_client/sandbox_v2/__init__.py`
- `sandbox_v2/hass_client/hass_client/sandbox_v2/__main__.py`
- `tests/components/sandbox_v2/test_manager.py`
- `sandbox_v2/hass_client/tests/__init__.py`
- `sandbox_v2/hass_client/tests/test_sandbox_runtime.py`

Files changed:
- `sandbox_v2/plan.md` — Phase 3 section marked complete with summary;
  health-protocol items left unchecked with a deferral note.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` → **28 passed**
  (3 new manager tests + the 25 existing Phase 0/1/2 tests).
- `cd sandbox_v2/hass_client && uv run pytest -q` → **3 passed**
  (ready-marker constant, CLI parser, runtime shutdown).
- `uv run prek run --files <changed files>` → all hooks pass
  (ruff-check, ruff-format, mypy, pylint, codespell, prettier).

Things to flag for the next phase:

- The `sandbox_v2/ping` health protocol checkbox is intentionally left
  unchecked. Phase 3's prompt scoped the websocket transport out, and
  the ping round-trip belongs with that transport. Process-exit
  detection in `SandboxProcess._supervise` covers the "hard crash"
  flavour of unhealthiness in the meantime — Phase 4 needs to add the
  ping handler on top.
- `SandboxManager._default_command` ships with placeholder `--url` and
  `--token` values (`ws://localhost:8123/api/websocket`,
  `sandbox_v2_placeholder`). The runtime accepts but does not yet use
  them — Phase 4 wires the real auth flow (the scoped sandbox token is
  Phase 7 work, but Phase 4 needs at least a working long-lived token
  to bootstrap).
- `SandboxManager` is not yet hooked into `async_setup` /
  `EVENT_HOMEASSISTANT_STOP`. Tests clean up explicitly with
  `async_stop_all`; Phase 4 will mount the manager on
  `SandboxV2Data.manager` and register the stop listener so production
  HA shuts down sandboxes cleanly.
- `READY_MARKER` is duplicated between
  `homeassistant/components/sandbox_v2/manager.py` and
  `hass_client/sandbox.py` (with cross-referencing comments) rather
  than imported across the package boundary. This avoids HA Core
  importing from `hass_client` at integration-load time. If Phase 4
  ends up sharing more protocol constants, consolidating them into a
  small shared module is worth considering.
- The `from __future__ import annotations` lines that ruff rewrote out
  of every new file are noted only because the surrounding sandbox_v2
  files do still carry them — the existing Phase 0/2 files predate the
  TID251 rule and may want a follow-up sweep. Not blocking.
