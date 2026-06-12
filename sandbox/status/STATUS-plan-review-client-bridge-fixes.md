# STATUS — plan-review-client-bridge-fixes (review follow-up #3 of 5)

**Outcome: COMPLETE.** All 7 phases shipped, each as its own commit. Commits
land on `sandbox` locally (not pushed — the orchestrator pushes). A regression
test accompanies every fix; both suites and the proto drift guard are green.

This plan is the *client-runtime + wire-fidelity* batch: contained,
independent correctness fixes, almost entirely under
`sandbox/hass_client/`, plus the `messages.py` int-fidelity fix that spans
both hand-mirrored copies.

## What each phase shipped

- **Phase 1 — replay services registered during setup**
  (`approved_domains.py`, `service_mirror.py`). `EVENT_SERVICE_REGISTERED`
  fires synchronously inside `async_setup_entry`, before the entry runner
  approves the domain, so `ServiceMirror` dropped those early registrations and
  never replayed them. `ApprovedDomains` now fires approve-listeners on the
  first (absent→present) `add`; `ServiceMirror` subscribes
  `async_sync_domain`, which re-mirrors every already-registered service of the
  freshly-approved domain (skipping any already in `_mirrored`). Covers both the
  entry-runner approve path and the entity-bridge per-entity approve path.
  **EventMirror left as-is** — owned events are transient; a past event cannot
  be replayed (noted as lower-risk in the plan).

- **Phase 2 — register handlers before sending Ready** (`sandbox/__init__.py`).
  The runtime pushed `Ready` (manager flips to running → router sends
  `entry_setup`), then awaited the warm-load `store_load`, and only afterwards
  registered `MSG_ENTRY_SETUP` et al — so an `entry_setup` in that window hit
  `ChannelUnknownType` → `SETUP_ERROR`. New order: register every inbound
  handler first, run the (outbound) warm-load `store_load`, then push `Ready`
  **last**. This removes the no-handler race *and* preserves the
  warm-load-before-entry_setup invariant (Ready timing still gates `entry_setup`
  until the restore cache is warm). The belt-and-suspenders queue option was not
  needed.

- **Phase 3 — flush coalesced state + handle removal mid-register**
  (`entity_bridge.py`). While an entity sat in `_pending` (register RPC in
  flight) `_on_state_changed` dropped every further `state_changed`, and the
  register task only pushed the snapshot captured at task-creation — a fast
  second update was lost, and a removal in the window left a ghost proxy. After
  the register RPC resolves, the task now (a) if a removal raced (new
  `_removed_while_pending` flag), unregisters the entity it just registered, and
  (b) otherwise re-reads `hass.states` and pushes a `state_changed` when the live
  state differs from the registered snapshot, flushing the gap.
  **Approach = correctness fix only.** See the plan-5 handoff note below.

- **Phase 4 — flush shutdown reply before closing the channel**
  (`channel.py` ×2, `sandbox/__init__.py`). `_handle_shutdown` set the shutdown
  event via `call_soon` so the reply lands first, but `call_soon` only buys one
  loop turn — if the reply write suspended (write-lock contention from unload
  pushes, drain backpressure on a large `restore_state`), `run()`'s finally
  closed the channel and cancelled the in-flight reply task, losing
  `restore_state`. Added **`Channel.drain_inflight(timeout)`**: wait for
  in-flight inbound handler tasks (the shutdown reply included) to finish before
  close, cancelling nothing. `run()`'s finally drains before `close()`.
  *Write-lock check (plan bullet 2):* `_write_lock` is a plain mutex held only
  across one frame write, so the shutdown reply and the unload-driven
  `_push_unregister` writes serialize — no circular wait, no deadlock; the
  unregister tasks are independent outbound `create_task`s, not channel inflight
  handlers, so they don't gate the drain.

- **Phase 5 — release `ApprovedDomains` approval on entity unregister**
  (`entity_bridge.py`). `_register` added an approval refcount per entity
  (`approved.add(domain)`) with no matching decrement, so a platform domain
  stayed approved for the process lifetime. Track each entity's contributed
  domain (`_approved_domain`) and release it (`_release_approval` →
  `approved.remove`) on both unregister paths (the `new_state is None` removal
  and the Phase 3 removal-while-pending flush). Symmetric with the per-entity
  add. **EntryRunner unchanged**: its per-entry `approved.remove(entry.domain)`
  on `entry_unload` already balances the per-entry `add` in `entry_setup`; only
  the entity-bridge call site was missing.

- **Phase 6 — drop a failed entry so `entry_setup` can be retried**
  (`entry_runner.py`). A failed `async_setup` left the rebuilt `ConfigEntry` in
  the sandbox's `config_entries` (only unload popped it), so main's retry of the
  same `entry_id` was rejected with "entry already loaded." On both failure
  paths (raised / returned `False`) the entry is now popped before returning
  `ok=False`. This is the **sandbox-side half of plan 1's SETUP_RETRY
  decision** — main shipped honest `SETUP_ERROR` + manual reload and remains the
  only retry driver. The sandbox-side `ConfigEntryNotReady` retry timer is
  deliberately **not** enabled (the sandbox hass is never `async_start`-ed).

- **Phase 7 — restore int types across the Struct wire** (`messages.py`,
  **both mirrors**). `protobuf.Struct` stores all numbers as `double`, so
  `_value_to_py` returned `entry.data` ints, `service_data` ints and the store
  envelope's `version`/`minor_version` as floats — breaking
  `socket`/`isinstance(int)`/`range(...)`. `_value_to_py` now coerces
  whole-number floats back to int (`int(v) if v.is_integer() else v`);
  fractional values keep their float type.

## messages.py — both-mirrors note

`messages.py` is hand-mirrored: `homeassistant/components/sandbox/messages.py`
(main) and `sandbox/hass_client/hass_client/messages.py` (client). The Phase 7
`_value_to_py` int-coercion **and** the updated "Numbers note" docstring were
applied **byte-identically** to both copies, verified with
`diff <main> <client>` → identical. No automated drift guard covers
`messages.py` (the proto guard only regenerates `_proto` gencode), so the
identity was checked by hand.

## Phase 7 int-coercion — narrowing decision

**No narrowing applied — global coercion kept.** Reviewed every
`struct_to_dict` / `listvalue_to_list` consumer on both sides (flow
`context`/`data`/`user_input`, `entry.data`/`options`, `service_data`/`target`,
`entity_query` args/result, store envelope `data`, state `attributes`,
`capabilities`, `event_data`, translations) — none requires a whole-number
float to stay a float. The explicit `int32` proto fields (`version`,
`minor_version`, `supported_features` on `EntrySetup`) bypass the Struct and are
unaffected. Genuinely fractional values (e.g. `0.5`, `target_temp_step`) keep
their float type, so the coercion only restores the int the sender meant.

## Phase 3 entity_bridge approach + plan-5 handoff

Phase 3 is implemented as the **correctness fix**, not the performance refactor:
the register task re-reads `hass.states` after the register RPC completes and
flushes a `state_changed` if the live state diverged from the registered
snapshot, and an explicit `_removed_while_pending` flag drives a post-register
unregister so a removal-in-the-window leaves no ghost proxy. **Plan 5
(simplification) builds a single-writer queue on top of this entity push path**;
when it lands it should subsume this flush into the queue's ordering guarantees.
This handoff is noted in-code (`entity_bridge.py`, `_register_and_push`) and in
the Phase 3 commit message.

## Tests added

- `test_service_mirror.py::test_service_registered_before_approval_is_replayed`
  (Phase 1)
- `test_sandbox_runtime.py::test_handlers_registered_before_ready` (Phase 2)
- `test_entity_bridge.py::test_state_update_during_register_is_flushed`,
  `::test_removal_during_register_unregisters` (Phase 3)
- `test_shutdown.py::test_shutdown_reply_flushes_despite_stalled_drain` (Phase 4;
  confirmed it fails with `ChannelClosedError` when the `drain_inflight` step is
  removed)
- `test_entity_bridge.py::test_unregister_releases_domain_approval` (Phase 5;
  `ApprovedDomains` add/remove symmetry also covered by the existing
  `test_approved_domains.py::test_remove_respects_refcount`)
- `test_entry_runner.py::test_failed_entry_setup_is_retryable` (Phase 6)
- `test_messages.py` (client) + `tests/components/sandbox/test_messages.py`
  (main mirror) for int/float wire fidelity; plus int assertions added to
  `test_entry_runner.py` for `entry.data` (`port`) and `service_data`
  (`brightness`) (Phase 7)

## Final verification

```
uv run pytest sandbox/hass_client/ -q
  98 passed, 1 warning in 0.59s

uv run pytest tests/components/sandbox/ --no-cov -q
  240 passed, 2 warnings in 8.24s
  (incl. test_proto_transport.py::test_protobuf_codec_round_trip_is_byte_identical,
   the known intermittent flake — passed this run)

bash sandbox/proto/check_drift.sh
  sandbox proto drift guard: gencode matches sandbox.proto.

uv run prek run --files <all changed files>
  exit 0 — clean (ruff / ruff-format / codespell / prettier / mypy / pylint all Passed)
```
