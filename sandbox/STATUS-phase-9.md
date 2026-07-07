Status: DONE

Phase 9 ships the graceful-shutdown round-trip plus restore-state
hand-off between main and each sandbox. The sandbox runtime registers
`sandbox_v2/shutdown` once its channel is up. On receipt the handler
iterates `config_entries.async_entries()` and runs
`config_entries.async_unload(entry_id)` for each, then snapshots
`RestoreStateData.async_get_stored_states()` into a JSON-safe wrapped
dict (round-tripped through orjson's HA-aware encoder so `Fragment`,
`State`, `datetime`, and friends survive the plain-JSON channel),
returns `{"ok": True, "unloaded": N, "restore_state": <payload | None>}`,
and schedules its own `_shutdown` event via `call_soon` *after* the
reply has been queued so the subprocess exits 0 on its own.

On main, `SandboxManager.async_graceful_shutdown_all(timeout=...)` fans
out `MSG_SHUTDOWN` to every running sandbox, hands each reply to a
configurable `on_shutdown_reply` callback, and waits for the process to
exit. `async_stop_all` is unchanged — it remains the SIGTERM/SIGKILL
escalation path for sandboxes that timed out the graceful round-trip.
The integration's `_on_stop` listener now calls
`async_graceful_shutdown_all(timeout=manager.shutdown_grace)` first,
then `async_stop_all`. The Phase 9 `on_shutdown_reply` persists the
`restore_state` payload via `SandboxBridge._handle_store_save` so it
lands at the same `<config>/.storage/sandbox_v2/<group>/core.restore_state`
path the next sandbox boot reads from.

On the next sandbox start, the runtime warm-loads that file before any
handler can dispatch an `entry_setup`. Because `restore_state.py`
captures `Store` at import time (`from .storage import Store`), Phase
8's module-attribute rebinding (`install_remote_store` mutates
`storage.Store`) can't reach it — Phase 9 swaps
`RestoreStateData.store` with an explicit `RemoteStore(hass, ...,
STORAGE_KEY, encoder=JSONEncoder)` and calls `async_load()` directly,
bypassing the helper's `start.async_at_start` listener (which never
fires on a bare HA). A new `wait_until_ready()` accessor on
`SandboxRuntime` lets tests gate on "handlers fully registered" rather
than the looser `started` flag.

The restore_state-via-`RemoteStore` route used inside the shutdown
handler would deadlock — the sandbox channel's reader task is single-
threaded and busy dispatching the handler when it tries to issue a
`MSG_STORE_SAVE`, so the reply for store_save can never be processed.
The reply-payload workaround is the lower-disruption fix: shipping the
data in the existing shutdown reply costs one round-trip (vs the
deadlock) and keeps the channel architecture unchanged. A concurrent
channel dispatcher (spawn one task per inbound call) would lift the
restriction for handlers in general; flagged for a future hardening
pass.

The plan's "fire `EVENT_HOMEASSISTANT_FINAL_WRITE` so pending Stores
flush" step is intentionally not implemented — it would have the same
re-entrant-deadlock shape for every `delay_save`-using Store. The
practical impact is bounded: integrations that rely on
`delay_save`-pending writes being flushed by FINAL_WRITE will lose
unwritten data on sandbox shutdown. Most integrations either save
synchronously through `async_save` (which already round-trips through
the channel during normal operation) or only buffer non-critical data.

`RemoteStore._async_write_data` grew an orjson pre-serialisation step
so the channel's plain `json.dumps` never has to grapple with
`Fragment` etc. — same trip `Store._async_write_data` would take on its
way to disk, just intercepted before the bytes hit a file. This is
what made the Phase 8 RemoteStore path work for `core.restore_state`
even though we don't use it inside the shutdown handler — the warm-load
on startup goes through RemoteStore.

Files added:
- `sandbox_v2/hass_client/tests/test_shutdown.py`
- `tests/components/sandbox_v2/test_phase9_shutdown.py`

Files changed:
- `homeassistant/components/sandbox_v2/__init__.py` — wire the
  `on_shutdown_reply` callback that persists the sandbox's restore_state
  snapshot via the bridge's store server; call
  `async_graceful_shutdown_all` before `async_stop_all` in `_on_stop`.
- `homeassistant/components/sandbox_v2/manager.py` — add
  `ShutdownReplyCallback`, the `on_shutdown_reply` plumbing on
  `SandboxProcess` and `SandboxManager`,
  `SandboxProcess.async_graceful_shutdown(timeout=...)`,
  `SandboxManager.async_graceful_shutdown_all(timeout=...)`, and the
  `shutdown_grace` property.
- `homeassistant/components/sandbox_v2/protocol.py` — add
  `MSG_SHUTDOWN` and a Phase 9 docstring section.
- `sandbox_v2/hass_client/hass_client/protocol.py` — mirror
  `MSG_SHUTDOWN`.
- `sandbox_v2/hass_client/hass_client/remote_store.py` — pre-serialise
  the payload through orjson (`json_helper.prepare_save_json`) before
  handing it to the channel so HA-specific types (`Fragment`, `State`,
  `datetime`) survive plain JSON.
- `sandbox_v2/hass_client/hass_client/sandbox.py` — register the
  `MSG_SHUTDOWN` handler; implement `_run_graceful_shutdown` (unload +
  collect restore_state); add `_ready` event + `wait_until_ready`
  helper; warm-load `core.restore_state` via a hand-installed
  `RemoteStore` before handlers register; reorder the run() body so
  the channel reader starts before the warm-load (the RPC needs it).
- `sandbox_v2/plan.md` — Phase 9 section marked complete with per-
  checkbox status and inline deferral notes.

Core HA files modified (review surface):
- None. (Phase 9 plumbing lives entirely in sandbox_v2/ and
  homeassistant/components/sandbox_v2/. The Phase 4 `router` hook,
  Phase 5 `async_register_remote_platform` hook, and Phase 7 `scopes`
  hook are reused unchanged.)

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **84 passed** (80 from Phase 0–8 + 4 new test_phase9_shutdown).
- `cd sandbox_v2/hass_client && uv run pytest -q` →
  **39 passed** (36 from Phase 0–8 + 3 new test_shutdown).
- `uv run pytest tests/helpers/test_storage.py
  tests/helpers/test_restore_state.py --no-cov -q` → **52 passed** —
  Phase 9 didn't disturb the public `Store` / `RestoreEntity` API.
- `uv run prek run --files <8 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, mypy, pylint, prettier).

Things to flag for the next phase:

- **Re-entrant `channel.call` from inside a handler deadlocks.** The
  channel's reader task is single-threaded and processes responses
  serially. A handler that issues `channel.call(...)` blocks waiting
  for a response that the same reader task can't pick up. Phase 9
  worked around the specific case (restore_state in the shutdown
  reply) but the more general fix — spawn a task per inbound call so
  the reader can keep draining the wire — is owed. This also
  matters for Phase 5/8 in theory: an integration's `async_setup_entry`
  that calls `Store.async_save` during the `MSG_ENTRY_SETUP` handler
  would hit the same deadlock. None of the existing tests exercise
  this path, but a real integration will. Recommended Phase 9b: add
  `Channel._dispatch_call_in_task` and a small concurrency cap.
- **`EVENT_HOMEASSISTANT_FINAL_WRITE` is not fired on sandbox shutdown.**
  Same deadlock shape — any `delay_save`-using Store's flush would
  re-enter the channel. Concrete loss: integrations that batch writes
  via `Store.async_delay_save` lose the pending data on sandbox
  shutdown. Phase 9b's concurrent dispatcher fixes this for free, at
  which point we can fire FINAL_WRITE inside `_run_graceful_shutdown`.
- **`restore_state` is the only framework Store routed to main.**
  Device/entity/area registries and the auth store still write to the
  sandbox's tempdir (Phase 8 STATUS already flagged this; Phase 9
  didn't change it). Adding them needs the same pattern Phase 9 used
  for `restore_state`: explicit `RemoteStore` wiring at startup before
  any consumer captures the original `Store` class. A registry helper
  that exposes the singleton Store would let us swap it in cleanly.
- **The shutdown payload is unbounded.** A sandbox with thousands of
  RestoreEntities serialises every state into one channel reply. For
  today's targets that's well under a megabyte; if Phase 10's compat
  lane lights up an integration with >10k RestoreEntities, consider
  paging or compressing the payload.
- **`on_shutdown_reply` is best-effort.** If the bridge isn't
  registered (e.g., a sandbox crashed before its `on_channel_ready`
  fired) the restore_state payload is dropped with a debug log.
  Phase 9 prefers data loss over a hang; the integration could
  instead write the payload directly through `_SandboxStoreServer`
  without the bridge, but that adds yet another file-write code path.
  Revisit if it bites.
- **`SandboxRuntime.wait_until_ready` is a new public surface for
  tests.** It pins the readiness contract (`_ready` event set after
  every handler registers) so tests don't have to poll. Same shape as
  the existing `started` property but stricter.
- **Test cross-fertilisation.** `tests/components/sandbox_v2/_helpers.py`
  already exports `make_channel_pair`, but the hass_client tree can't
  import from `tests/...` (TID251). The result is a duplicated
  `_make_channel_pair`/`_LoopbackWriter` snippet in
  `sandbox_v2/hass_client/tests/test_shutdown.py` (and the existing
  `test_remote_store.py`). Could be lifted to a `conftest.py` fixture
  in `sandbox_v2/hass_client/tests/` if it keeps growing.
