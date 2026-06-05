Status: DONE

Phase 12 lifts the single-threaded-reader limitation Phase 9 flagged.
Both `Channel` classes (the HA-Core integration's at
`homeassistant/components/sandbox_v2/channel.py` and the sandbox
runtime's at `sandbox_v2/hass_client/hass_client/channel.py`) now
dispatch each inbound call or push in its own
`asyncio.create_task`, freeing the reader to keep draining the wire.
The synchronous-response path (a reply to one of our own calls) is
unchanged — those still set the pending future inline, since there is
no I/O to do.

A bounded `asyncio.Semaphore` caps concurrent handler tasks; the
default is `DEFAULT_MAX_INFLIGHT = 16` and the new `max_inflight`
keyword on `Channel.__init__` lets tests dial it down. The semaphore
is acquired *inside* the dispatched task (not in the read loop), so
the reader keeps making forward progress even when the cap is hit —
the (cap+1)th call simply queues at the semaphore until a slot frees,
matching the plan's "queues until earlier completes" requirement.

`Channel.close()` now cancels every tracked in-flight handler task
and awaits them via `asyncio.gather(..., return_exceptions=True)`
after the writer and reader teardown. The read loop's `finally` also
cancels in-flight tasks on EOF so a remotely-closed channel doesn't
leave handlers running against a dead writer. The
`test_close_cancels_inflight_calls` semantics from Phase 0 still hold:
the *caller* sees `ChannelClosedError` while the remote handler task
is cancelled.

With concurrent dispatch in place,
`SandboxRuntime._run_graceful_shutdown` now sets
`hass.state = CoreState.final_write`, fires
`EVENT_HOMEASSISTANT_FINAL_WRITE`, and `await hass.async_block_till_done()`
right after unloading entries. Each pending `async_delay_save` Store
runs its FINAL_WRITE listener, which calls `_async_handle_write_data`,
which (with `install_remote_store` already in effect) round-trips
through `MSG_STORE_SAVE` — the reader picks the reply up immediately
because it's no longer blocked on the shutdown handler. The
restore-state-via-reply path from Phase 9 stays in place because
`core.restore_state` is owned by the runtime's explicit warm-load /
shutdown-dump path, not by an integration's `Store`.

Files added:
- `sandbox_v2/STATUS-phase-12.md`

Files changed:
- `homeassistant/components/sandbox_v2/channel.py` — concurrent
  dispatch + bounded semaphore + in-flight tracking; `close()` cancels
  and awaits handler tasks. Updated module docstring.
- `sandbox_v2/hass_client/hass_client/channel.py` — same changes
  mirrored on the sandbox side.
- `sandbox_v2/hass_client/hass_client/sandbox.py` — fire
  `EVENT_HOMEASSISTANT_FINAL_WRITE` from `_run_graceful_shutdown`;
  set `CoreState.final_write` first and `await hass.async_block_till_done()`
  so re-entrant `RemoteStore` flushes complete. Updated docstring.
- `tests/components/sandbox_v2/_helpers.py` — `make_channel_pair`
  grew `max_inflight_a` / `max_inflight_b` keywords so tests can
  exercise the cap path.
- `tests/components/sandbox_v2/test_channel.py` — added
  `test_handler_can_call_back_without_deadlock` and
  `test_concurrency_cap_queues_excess_handlers`.
- `sandbox_v2/hass_client/tests/test_shutdown.py` — added
  `test_shutdown_fires_final_write_event` and
  `test_shutdown_flushes_pending_delay_save`; switched the storage
  import to look up `Store` dynamically via `_storage.Store` so the
  `install_remote_store` patch is honoured.
- `sandbox_v2/plan.md` — Phase 12 section marked ✅ COMPLETE with a
  summary paragraph and per-checkbox status.

Core HA files modified (review surface):
- None. Phase 12 lives entirely under `sandbox_v2/` and
  `homeassistant/components/sandbox_v2/`. The Phase 4 / 5 / 7 core
  hooks are reused unchanged.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **93 passed** (91 from prior phases + 2 new channel tests).
- `cd sandbox_v2/hass_client && uv run pytest -q` →
  **45 passed** (43 from prior phases + 2 new shutdown tests).
- `uv run prek run --files <6 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, prettier, mypy, pylint).

Things to flag for the next phase:

- **`EVENT_HOMEASSISTANT_FINAL_WRITE` happens before `core.restore_state`
  collection.** Order was deliberate — flush integration Stores first
  (a misbehaving listener can no longer hang us thanks to Phase 12),
  then snapshot RestoreEntities. If a future integration produces
  restore-state updates from inside its FINAL_WRITE listener, the
  snapshot will see them. If anyone wants the opposite order, the
  block in `_run_graceful_shutdown` is one move.
- **`hass.state` is mutated to `CoreState.final_write` inside the
  shutdown handler.** The sandbox-private `HomeAssistant` doesn't go
  through `async_start` / `async_stop`, so this is the first time its
  state changes from `not_running`. The bus and task system don't
  care, but if a future integration reads `hass.state` and adapts its
  behaviour, expect it to see `final_write` during shutdown — same
  signal a real HA instance would emit.
- **Cap is process-wide, not per-message-type.** The default 16 was
  picked because it matches the order of magnitude of concurrent
  channel work the runtime would realistically see (one per loaded
  entry plus a few service / state pushes). If a single noisy push
  type ever needs throttling independent of calls, a per-type
  semaphore would slot in alongside `_inflight_sem` without churning
  the dispatch shape.
- **Re-entrancy now works for any handler.** Phase 5/8's theoretical
  worry — an integration's `async_setup_entry` doing `Store.async_save`
  during `MSG_ENTRY_SETUP` — is now safe. No existing test directly
  exercises that path, but Phase 13's per-domain proxy tests are the
  natural place to add one if it becomes load-bearing.
- **`_helpers.py::make_channel_pair` now takes
  `max_inflight_a` / `max_inflight_b`.** New surface area for tests
  to exercise the cap; only the new `test_concurrency_cap_queues_excess_handlers`
  uses it today. The `tests/components/sandbox_v2/` tree is the only
  consumer.
- **`test_shutdown.py`'s `Store` resolution.** The new
  `test_shutdown_flushes_pending_delay_save` switched to
  `from homeassistant.helpers import storage as _storage` plus
  `_storage.Store(...)` so it picks up the `install_remote_store`
  patch. Integration authors who `from homeassistant.helpers.storage
  import Store` at module-import time before the patch installs will
  still capture the original `Store` — Phase 8 STATUS already flagged
  this as a known sharp edge.
- **Phase 9's "concurrent channel dispatcher" follow-up is now
  closed.** Update Phase 9's STATUS callout if any future doc sweep
  passes through that file.
