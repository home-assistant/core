Status: DONE

Phase 8 routes sandbox-side `Store` operations to main over the
existing control channel. A new `RemoteStore` (in
`sandbox_v2/hass_client/hass_client/remote_store.py`) subclasses
`homeassistant.helpers.storage.Store` and overrides the three IO
primitives — `_async_load_data`, `_async_write_data`, and
`async_remove` — to talk to main via `sandbox_v2/store_load`,
`sandbox_v2/store_save`, and `sandbox_v2/store_remove`. The sandbox
runtime calls `install_remote_store(channel)` right after the channel
opens and right before the per-runner handlers register, so every
`Store(...)` instantiated during `async_setup_entry` is a RemoteStore.
The patch is process-wide (a class-level `RemoteStore._channel` plus a
rebinding of `homeassistant.helpers.storage.Store`), since one sandbox
process hosts one sandbox group. On shutdown the uninstall callable
restores the original `Store` class and clears the channel reference.

Migration, `delay_save`, the EVENT_HOMEASSISTANT_FINAL_WRITE hook, and
the corruption-handling paths from `Store` are all reused unchanged —
`RemoteStore` only swaps the disk-IO primitives for channel calls. The
migration block in `_async_load_data` is copied from `Store` because
the source method doesn't expose a hook to plug the load source; this
is the load-bearing duplication (with an inline note pointing to the
parent method) for the phase.

On main each `SandboxBridge` owns a `_SandboxStoreServer` pinned to
`<config>/.storage/sandbox_v2/<group>/`. Reads use
`json_util.load_json` with a `None` default; writes use
`util.file.write_utf8_file_atomic` (same primitive `Store` uses); removes
unlink the file. Key validation (`_require_key`) rejects `/`, `\`, NUL,
`.`, `..`, and any `..`-prefixed key before any path is constructed.
Scope isolation is by construction: each bridge owns one channel for
one group, so a sandbox cannot reach another sandbox's files —
forging a cross-group call would require forging the channel itself.

Files added:
- `sandbox_v2/hass_client/hass_client/remote_store.py`
- `sandbox_v2/hass_client/tests/test_remote_store.py`
- `tests/components/sandbox_v2/test_store.py`

Files changed:
- `homeassistant/components/sandbox_v2/protocol.py` — add
  `MSG_STORE_LOAD` / `MSG_STORE_SAVE` / `MSG_STORE_REMOVE` constants
  + docstring entries.
- `homeassistant/components/sandbox_v2/bridge.py` — add the three
  store handlers on `SandboxBridge`, the `_SandboxStoreServer`
  per-group backend, and the `_require_key` validator. Phase 8 note
  added to the module docstring.
- `sandbox_v2/hass_client/hass_client/protocol.py` — mirror the new
  message constants.
- `sandbox_v2/hass_client/hass_client/sandbox.py` — call
  `install_remote_store(channel)` after the channel is built, and
  uninstall on shutdown.
- `sandbox_v2/plan.md` — Phase 8 section marked complete with
  per-checkbox status + inline notes for the deferrals.

Core HA files modified (review surface):
- None. (Phase 8 is sandbox-side plus integration-local handlers on
  main. The bridge uses the existing public surface of
  `homeassistant.helpers.storage` and `homeassistant.util.file`.)

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` →
  **80 passed** (67 from Phase 0–7 + 13 new test_store).
- `cd sandbox_v2/hass_client && uv run pytest -q` →
  **36 passed** (30 from Phase 0–7 + 6 new test_remote_store).
- `uv run pytest tests/helpers/test_storage.py --no-cov -q` →
  **39 passed** — Phase 8 didn't disturb the public `Store` API.
- `uv run prek run --files <7 changed files>` → all hooks pass
  (ruff-check, ruff-format, codespell, mypy, pylint, prettier).

Things to flag for the next phase:

- **`install_remote_store` is a process-wide rebinding.** It mutates
  `homeassistant.helpers.storage.Store` so every `Store(...)`
  instantiation in the sandbox process after the patch returns a
  `RemoteStore`. Two tests in `test_remote_store.py` exercise the
  install/uninstall cycle and confirm the patch is reverted, but any
  code path that captures `Store` at module-import time *before* the
  patch (or after the uninstall) will keep the original class. In
  practice this is harmless: registries that loaded before the patch
  keep their tempdir backing, and integrations import `Store` lazily
  during their own `async_setup_entry`.
- **Migration logic is duplicated from `Store._async_load_data`.**
  The base class doesn't expose a hook to override only the disk-read
  step, so `RemoteStore._async_load_data` copies the migration block
  verbatim. If the upstream block grows (new fields, new migration
  shape), the copy needs to follow. A future hardening pass could
  refactor `Store` to extract `_read_wrapped_payload()` as a
  one-liner override point.
- **`Store.path` still points at a local path on the sandbox tempdir.**
  RemoteStore inherits the `@cached_property` — the path it returns
  doesn't exist on disk. No RemoteStore code path uses it; integrations
  that read `store.path` directly (rare, mostly for logging) will see
  a meaningless string. If this trips a real integration, override
  `path` to emit a remote-flavoured sentinel.
- **Phase 9's shutdown protocol needs to force-flush every RemoteStore.**
  `Store` writes pending data on `EVENT_HOMEASSISTANT_FINAL_WRITE`,
  but Phase 8 doesn't wire that event up on the sandbox side — the
  sandbox's HA instance isn't currently fired through the
  `homeassistant_final_write` step. Phase 9 should add a
  `flush_pending_writes()` pass over the per-process Store registry as
  part of the `sandbox_v2/shutdown` round-trip.
- **HA registries on the sandbox still write to the tempdir.**
  Device/entity/area/auth registries that load during the sandbox's
  startup (before the channel is up) keep their local file backing,
  so cross-restart persistence for those is lost when the tempdir
  is recreated. Phase 8 intentionally leaves this alone — integration
  state is what the plan calls out, and routing the HA-internals
  Stores too is a larger decision that depends on Phase 9/10 needs.
- **No back-pressure on `store_save` round-trips.** A flush waits for
  main's ack before resolving the future inside `_async_handle_write_data`'s
  write lock. If main is slow (or hung), the sandbox's `Store.async_save`
  call blocks accordingly — same shape as the local-disk slow-IO
  case. The 30s timeout knob in `Channel.call(...)` is available if a
  future phase wants to bound this.
- **Path-traversal validator is conservative.** `_require_key` rejects
  `.` / `..` / slashes / NUL outright. Real-world Store keys use only
  `[A-Za-z0-9_.]`-shaped strings (`auth`, `core.entity_registry`,
  `light.hue.entry_id`), all of which pass. If a future integration
  uses something exotic, the validator will need adjusting.
- **The locked-down sharing posture from Phase 7 still holds.** Stores
  are scoped per group, so `share_states=False` continues to apply at
  the bus level; Phase 8 doesn't change which data flows back to main.
