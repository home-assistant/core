# Plan — Client-side races & wire int-fidelity (review follow-up #4)

> Source: 2026-06-12 sandbox code review, client-runtime + wire-fidelity angles.
> Status notes go to `sandbox/status/STATUS-plan-review-client-bridge-fixes.md`.

## Goal

Fix a batch of smaller, independent client-side correctness bugs plus the
protobuf `Struct` int→float fidelity loss. Grouped because each is a contained
edit in the sandbox runtime / bridge; ordered within the plan by blast radius.

## Success criteria

- [ ] Services registered during `async_setup_entry` reach main.
- [ ] No `entry_setup` arriving right after `Ready` fails with "no handler".
- [ ] State updates / removals during an in-flight `register_entity` are not lost
      (no stale value, no ghost proxy).
- [ ] Graceful-shutdown `restore_state` reliably reaches main before the channel
      closes.
- [ ] `ApprovedDomains` approvals are released when their entities/entry go away.
- [ ] A failed `entry_setup` can be retried (no permanent "entry already loaded").
- [ ] Integer config / service-data / store-version values survive the wire as
      `int`, not `float`.
- [ ] Regression test per fix; both suites green; `uv run prek run` clean.

## Phase 1 — Replay services registered during setup

`EVENT_SERVICE_REGISTERED` fires synchronously while a service is registered
inside `async_setup_entry`, but `EntryRunner` only approves the domain *after*
`async_setup` returns (`entry_runner.py:113`), so `ServiceMirror`
(`service_mirror.py:83`) drops it with a warning and never replays.

- [ ] When a domain becomes approved (`ApprovedDomains.add` transitions a domain
      from absent→present), have `ServiceMirror` **replay** the now-eligible
      existing services: scan `hass.services.async_services()` for that domain and
      push `register_service` for each. Add a hook/callback on `ApprovedDomains`
      add, or call a `ServiceMirror.async_sync_domain(domain)` from `EntryRunner`
      right after `approved.add(entry.domain)`.
- [ ] Same consideration for `EventMirror` if any owned events could fire during
      setup before approval (lower risk — events are transient, but note it).

## Phase 2 — Register handlers before sending `Ready`

`SandboxRuntime.run` pushes `Ready` (manager flips to running, router sends
`entry_setup`), then awaits the warm-load `store_load` RPC, and only *afterwards*
registers `MSG_ENTRY_SETUP` (`sandbox/__init__.py:194`). An `entry_setup` in that
window gets `ChannelUnknownType` → `SETUP_ERROR`.

- [ ] Register all per-runtime call handlers (`entry_setup`, `flow_init`,
      `flow_step`, `flow_abort`, `entity_query`, `get_translations`, `shutdown`,
      `ping`) **before** pushing `Ready`. The warm-load `store_load` is an
      *outbound* call and doesn't need inbound handlers registered first, so it
      can stay where it is or move after registration — just ensure `Ready` is the
      last thing sent.
- [ ] Alternatively (belt-and-suspenders), have the channel **queue** unknown
      call types briefly instead of hard-erroring — but prefer the ordering fix;
      it's simpler and removes the race entirely.

## Phase 3 — Don't lose events while a register RPC is in flight

`_on_state_changed` returns without queuing while `entity_id in _pending`
(`entity_bridge.py:127`); the register task sends the snapshot captured at
task-creation and never re-reads. A fast second update is lost; a removal in the
window leaves a ghost proxy on main.

- [ ] After the `register_entity` RPC completes, **re-read the current state**
      from `hass.states` and push a `state_changed` if it differs from the
      snapshot that was registered (flush the coalesced gap).
- [ ] Handle removal-during-register: if the entity was removed while pending,
      after register completes, immediately push the unregister (or skip the add
      and unregister). Track a "removed while pending" flag rather than relying on
      `_registered` membership.
- [ ] Consider folding this into the single-writer-queue refactor (the simplification plan) — if
      the simplification plan lands first, implement the flush on top of the queue. Note the
      ordering in the commit.

## Phase 4 — Guarantee the shutdown reply flushes before close

`_handle_shutdown` schedules `_shutdown.set` via `call_soon` *before* its reply
is guaranteed written (`sandbox/__init__.py:259`); if the reply write suspends
(write-lock contention from unload pushes, or drain backpressure on a large
`restore_state`), `run()`'s `finally` closes the channel and cancels the in-flight
reply task → main loses `restore_state`.

- [ ] Ensure the shutdown handler's reply is fully written **before** the
      shutdown event is set / the channel closes. E.g. `await` the reply send
      inside the handler (don't rely on the post-return write), then schedule
      exit; or have `run()`'s finally drain pending writes before `close()`.
- [ ] Verify the unload-triggered `_push_unregister` calls during shutdown can't
      deadlock the write lock against the reply (order them, or make shutdown's
      reply take priority).

## Phase 5 — Release `ApprovedDomains` approvals

`.add` is called per registered entity (`entity_bridge.py:220`); the only
decrement is `entry.domain` on unload (`entry_runner.py:131`). Platform-domain
approvals leak for process lifetime, keeping the service/event gate open for
domains with zero owning entities.

- [ ] Decrement the refcount when an entity is unregistered (`_push_unregister`
      / `new_state is None` path) and on `entry_unload` for each domain the entry
      contributed — symmetric with the per-entity `.add`.
- [ ] Confirm `ApprovedDomains` is a true refcount (add N, remove N → absent);
      add the missing `.remove`/`.discard` call sites. Test add/remove symmetry.

## Phase 6 — Retry-able failed `entry_setup`

A failed `entry_setup` leaves the rebuilt `ConfigEntry` in the sandbox's
`config_entries` (only unload pops it, `entry_runner.py:99`), so main's later
retry of the same `entry_id` is rejected with "entry already loaded."

- [ ] On `async_setup_entry` failure (returns False / raises), **remove** the
      entry from the sandbox's `config_entries` before returning `ok=False`, so a
      re-sent `entry_setup` starts clean.
- [ ] Or make the `entry_setup` handler idempotent: if the entry exists but isn't
      loaded, tear it down and retry rather than rejecting.
- [ ] Cross-check with the crash-recovery plan's `SETUP_RETRY` decision — this is the sandbox-side
      half of making retries actually work.

## Phase 7 — Preserve integer types across the `Struct` wire

`protobuf.Struct` stores all numbers as `double`; `_value_to_py`
(`messages.py:72`) returns `number_value` raw, so `entry.data` ints
(`router.py:223`), `service_data` ints (`bridge.py:299`), and the store
envelope's `version`/`minor_version` (`sandbox_bridge.py:76`) arrive as floats.
Breaks `socket`/`isinstance(int)`/`range(min_version+1, …)`.

- [ ] In `_value_to_py` (`messages.py`, **both mirrors**), restore whole-number
      floats to `int`: `int(v) if v.is_integer() else v`. This is the smallest,
      broadest fix and matches HA's general JSON-number expectations.
      > Caveat: a value that is *legitimately* `1.0` becomes `1`. For HA config
      > this is almost always desired (HA stores ints as ints); confirm no
      > sandboxed path needs a float-typed whole number. If one does, prefer
      > carrying that field as an explicit typed proto field instead.
- [ ] Confirm the explicit int32 proto fields (`version`, `minor_version`,
      `supported_features` on `EntrySetup`) are unaffected — they already bypass
      the Struct and stay int. The store-envelope versions ride *inside* the
      Struct, so they're fixed by the `_value_to_py` change.
- [ ] Tests: round-trip `{"port": 8123}` through `entry.data` → assert `int`;
      store envelope `version=1` → assert `int` after load; a service call with an
      int field → assert `int` on the sandbox side.

## Verification

```bash
uv run pytest sandbox/hass_client/ -q
uv run pytest tests/components/sandbox/ --no-cov -q
bash sandbox/proto/check_drift.sh
uv run prek run --files <changed>
```

## Risks / open questions

1. **`messages.py` is hand-mirrored** — apply the Phase 7 `_value_to_py` change
   to both copies (the simplification plan adds the drift guard).
2. **Phase 3 vs the simplification plan** — both restructure the entity push path; sequence this
   plan first and let the simplification plan build the writer-queue on top, or vice-versa. Pick
   one ordering in the INDEX and note it.
3. **`is_integer()` global coercion** — verify no sandboxed integration depends
   on a whole-number float staying a float (rare). If found, narrow the fix to
   the affected fields.
4. **Phase 6 sandbox-private retry timer** — the sandbox hass is never
   `async_start`ed, so its own `ConfigEntryNotReady` retry never fires (verified);
   that means main is the only retry driver. Don't accidentally enable the
   sandbox-side timer.

## Out of scope

- The crash/restart lifecycle (the crash-recovery plan) and the trust-boundary gates (the trust-boundary plan).
- The single-writer-queue performance refactor (the simplification plan) — Phase 3 here is the
  *correctness* fix; the perf refactor is cleanup.
