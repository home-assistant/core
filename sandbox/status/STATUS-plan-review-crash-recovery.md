Status: DONE

Plan: `sandbox/plans/plan-review-crash-recovery.md` (review follow-up #1 of 5).
All six phases shipped + the regression suite. Branch `sandbox`, six local
commits (orchestrator pushes).

## Execution note (deviation from the brief)

The brief mandated executing via the `/phx:work` skill. That skill is
Elixir/Phoenix-specific (it reads `mix.exs` and runs `mix compile` / `mix
test`) and does not function on this Python / Home Assistant codebase. I
honoured its **intent** instead: phase-by-phase progress tracking (TaskCreate),
a per-step verify loop (`uv run pytest` after each change), and one commit per
logical phase, in plan order (1 keystone → 6). No ad-hoc multi-phase edits.

## What each phase shipped

### Phase 1 — tear down the old bridge on restart (keystone) — `e29f8e08458`
- **New public hook** `EntityComponent.async_unregister_remote_platform(config_entry)`
  in `homeassistant/helpers/entity_component.py` — the symmetric inverse of
  `async_register_remote_platform` (pops the entry's platform slot, returns it).
  This replaces the old `component._platforms.pop(...)  # noqa: SLF001` poke that
  `bridge.async_unload_entry` used → satisfies the Iron Law (public hook, no
  private-internals poke).
- `SandboxBridge.async_teardown()` + a shared `_async_teardown_entry(entry_id)`
  helper; `async_unload_entry` now routes through it. Teardown destroys each
  `EntityPlatform` (removing its proxy entities from the state machine) and
  unregisters it via the new hook.
- `__init__._on_channel_ready`: a restart stashes the displaced bridge in the
  new `SandboxData.pending_teardown[group]`; the new bridge is installed
  immediately (handlers must be live before the reader starts). A second crash
  before the first respawn goes ready tears down the earlier pending bridge so
  neither leaks.
- **Re-drive trigger**: new manager `on_ready(group)` callback, fired in
  `_supervise_until_exit` right after `_ready.set()` on every (re)spawn.
  `__init__._on_ready` tears down the stashed old bridge and re-drives setup for
  the group's still-`LOADED` entries via `async_schedule_reload`. Teardown is
  awaited **before** scheduling the reload, so the new platform registration
  can't collide with the still-registered old one. Capturing the loaded entries
  synchronously in `_on_ready` is what keeps a *first* start (entries not yet
  loaded) from being mistaken for a respawn and double-setting-up.

### Phase 2 — mark proxies unavailable when the sandbox dies — `bfc75a6cc1a`
- `SandboxBridge.async_mark_all_unavailable()` flips every owned proxy via the
  already-present (but previously caller-less) `sandbox_set_available(False)`.
- New manager `on_channel_closed(group)` callback, fired in
  `_supervise_until_exit` right after the control channel is closed on process
  exit. `__init__._on_channel_closed` marks the group's live bridge unavailable.
  Proxies recover to available on respawn through the normal
  register/`state_changed` round-trip (chosen option (b): a manager callback,
  not a Channel on-close subscription — keeps `channel.py` untouched for this).

### Phase 3 — bound the two shutdown/respawn hangs in `manager.py` — `c89fbe78658`
- **stop() spawn-in-progress race**: extracted a `_terminate(proc)` helper
  (SIGTERM → grace → SIGKILL). The real fix is a **post-spawn `_stopping`
  check** in `_run_one_stdio` / `_run_one_unix`: a stop() that lands inside
  `_spawn` reads `self._process` as None and terminates nothing, so right after
  the child object lands we check `_stopping` and kill the child stop() missed
  rather than running it unsupervised. stop()'s `await supervisor` is also
  bounded (`ready_timeout + shutdown_grace`) with a SIGKILL + cancel backstop so
  no other slow-exit path can hang HA shutdown.
- **Respawn ready-timeout**: `_supervise_until_exit` now wraps the
  `asyncio.wait({ready, exit})` with `ready_timeout` on **every** attempt (not
  just the first `start()`); a child that opens its channel but never signals
  ready is killed and the attempt counts against the restart budget instead of
  leaving the sandbox `starting` forever.
- **No more `starting` zombie**: `start()`'s wait is refactored into a reusable
  `_wait_ready_or_stopped`; a new public `async_wait_until_ready` lets
  `ensure_started` **await** readiness for an in-flight (re)spawn (`starting`)
  and raise `SandboxFailedError` if it never becomes `running`, instead of
  handing back a process whose channel is open but unanswered.

### Phase 4 — don't leak the platform on unload-while-down — `d86cd3ea81a`
- `router.async_unload_entry` extracted a shared `_async_unload_main_side`
  helper (delegates to `bridge.async_unload_entry`, i.e. the Phase 1
  public-hook teardown). It now runs on the sandbox-down early return **and** on
  a `ChannelClosedError` mid-unload — both skip the impossible remote RPC but
  still remove the proxies + platform slot. A live sandbox that refuses the
  unload (`ChannelRemoteError`) still returns `False` with proxies intact.

### Phase 5 — `Channel.close()` no-op + SETUP_RETRY non-retry — `5867dec9904`
- **`Channel.close()`**: split "already closed" (set `_closed`, fail pending —
  idempotent) from "teardown not yet done" (close transport + await inflight),
  guarded by a new `_close_done` flag that runs the heavy teardown exactly once
  regardless of who set `_closed` first. The EOF path in the read loop sets
  `_closed` but can't close the transport (it runs inside the reader); `close()`
  now always finishes that, so the stdin pipe / unix connection no longer leaks
  every restart. **Applied to BOTH hand-mirrored `channel.py` copies** — main
  (`homeassistant/components/sandbox/channel.py`) and client
  (`sandbox/hass_client/hass_client/channel.py`); verified byte-identical
  `close()` bodies and the proto drift guard is clean.
- **SETUP_RETRY → SETUP_ERROR (deviation, as the plan's fallback allows)**: a
  true router-driven retry was **not feasible** from the router seam. The router
  runs in `ConfigEntries.async_setup` *outside* `ConfigEntry.async_setup`, which
  is where core arms the `SETUP_RETRY` timer (`async_call_later`); a
  router-set `SETUP_RETRY` therefore wedges the entry in a retry state that
  never fires (and a later `async_setup` raises `OperationNotAllowed`). Per the
  plan's explicit fallback, the `ChannelClosedError`-during-`entry_setup` case
  now reports `SETUP_ERROR` honestly ("…reload to retry"; the state is
  recoverable). `ARCHITECTURE.md` §5 updated to match (and to document the new
  on_ready re-drive + on_channel_closed unavailable behavior); a router-driven
  true retry is flagged as a follow-up.

### Phase 6 — regression tests — `d16080e9dcb`
- `tests/components/sandbox/test_crash_recovery.py` (new, 3 tests):
  crash→respawn→re-register with live state still flowing (Phase 1);
  proxy goes `unavailable` on death and recovers on respawn (Phase 2);
  unload-while-down releases the platform so a fresh bridge re-registers
  with no "has already been setup!" (Phase 4).
- `test_manager.py`: `test_stop_during_spawn_does_not_hang` — a
  `_PausingProcess` suspends inside `_spawn` so stop() lands while
  `self._process` is None; asserts stop() completes (no hang) and the child
  is terminated (Phase 3).
- `test_channel.py`: `test_close_after_eof_still_closes_transport` — feeds an
  inbound call (inflight handler) then EOF, asserts EOF did *not* close the
  transport, then `close()` closes it + awaits the cancelled inflight exactly
  once and is idempotent (Phase 5).

## Public / core-HA surface added
- `EntityComponent.async_unregister_remote_platform(config_entry)` — new `@callback`
  inverse hook (the only core-HA addition; `entity_component.py`).
- Three new internal manager callbacks (`on_ready`, `on_channel_closed`) +
  `SandboxProcess.async_wait_until_ready` — all within the sandbox integration.
- `SandboxData.pending_teardown` field.

## channel.py both-mirrors note
The `Channel.close()` fix was applied to **both** hand-mirrored copies (main +
`hass_client`), noted in commit `5867dec9904`. `diff` of the `close()` bodies is
identical; `bash sandbox/proto/check_drift.sh` → "gencode matches sandbox.proto".

## Final verification (all green)
- `uv run pytest tests/components/sandbox/ --no-cov -q` → **224 passed**, 2 warnings
- `uv run pytest sandbox/hass_client/ -q` → **87 passed**, 1 warning
- `uv run pytest tests/helpers/test_entity_component.py --no-cov -q` → **30 passed**
  (guards the new public hook)
- `bash sandbox/proto/check_drift.sh` → clean ("gencode matches sandbox.proto")
- `uv run prek run --files <all changed>` → ruff check / ruff format / codespell /
  prettier / mypy / pylint all **Passed**

## Follow-ups flagged
- Router-driven **true retry** for `ChannelClosedError`-during-`entry_setup`
  (currently honest `SETUP_ERROR` + manual reload). See `ARCHITECTURE.md` §5.
- `channel.py` stays hand-mirrored until plan 5's drift guard lands; the
  trust-boundary plan (plan 2) also edits `channel.py` (read backpressure) —
  whichever lands second rebases (noted in this plan's Risks).
