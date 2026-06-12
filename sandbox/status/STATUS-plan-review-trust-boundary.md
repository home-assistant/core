# STATUS — plan-review-trust-boundary (review follow-up #2 of 5)

**Outcome: COMPLETE.** All 8 phases shipped; every proposed gate is enforced on
main (none deferred or declined). Commits land on `sandbox` locally (not pushed
— the orchestrator pushes).

## The linchpin: one owned-domain derivation, reused

`SandboxBridge._owned_domains()` (`bridge.py`) is the single source of "domains
this group owns," derived **only from main-side state** — never a
sandbox-supplied identifier:

- the integration `domain` of every config entry with `entry.sandbox == self.group`, plus
- the platform domains of the proxy entities this bridge has registered.

It is `@callback`, synchronous, and reads `config_entries.async_entries()` (an
in-memory list — no async registry race). The `fire_event` (Phase 1) and
`register_service` (Phase 2) gates both consult it, so they cannot disagree.
The `register_entity` gate (Phase 3) uses the per-entry form (`entry.sandbox ==
self.group`) plus a sibling `_owned_entry_ids()` helper for the device-merge
check.

## What each phase shipped

- **Phase 1 — fire_event domain gate** (`_handle_fire_event` / `_is_event_allowed`).
  An event is re-fired only when its name is in an owned `<domain>_` namespace
  **and** is not a hard-denied core/control-plane event
  (`_DENIED_EVENT_TYPES`: `homeassistant_*`, `call_service`, `state_changed`,
  `state_reported`, `service_registered/removed`, `component_loaded`,
  `core_config_updated`). A forged event is logged + dropped — never raised into
  the dispatch loop (it's a one-way push).
- **Phase 2 — register_service ownership** (`_handle_register_service`). The
  service `domain` must be owned; otherwise rejected with a `HomeAssistantError`
  → remote-error frame. The existing refuse-to-clobber-an-existing-handler check
  is kept.
- **Phase 3 — register_entity entry/group ownership** (`_handle_register_entity`
  / `_reject_foreign_device_merge`). Requires `entry.sandbox == self.group` (not
  just a resolvable id). A `device_info` whose identifiers/connections collide
  with a device already owned by a config entry **outside** this group is refused
  rather than merged (device-registry hijack vector). `entry_setup` /
  `entry_unload` are main-initiated (main supplies the entry_id) and the store
  server is one-dir-per-channel by construction, so no other entry_id trust
  point needed gating — confirmed.
- **Phase 4 — translation returned ⊆ requested** (`translation.py`
  `async_get_translations`). The overlay keeps only the requested ∩ returned
  domain intersection, so a compromised sandbox can't return strings for a
  co-requested victim domain (`hue`, `http`) to poison its frontend strings.
- **Phase 5 — store quotas** (`_validate_key`, `_SandboxStoreServer._write_sync`
  / `_enforce_group_quota`). Key-length cap (`_STORE_MAX_KEY_LENGTH = 128`, well
  under `NAME_MAX`), per-key value cap (`_STORE_MAX_VALUE_BYTES = 4 MB`), and a
  per-group dir quota (`_STORE_MAX_TOTAL_BYTES = 32 MB`, `_STORE_MAX_KEYS =
  256`). Over-quota writes raise → remote-error frame; the sandbox-side
  `async_store_save` already catches `ChannelRemoteError` and logs (keeping its
  in-memory data), so a rejected flush **degrades, not crashes** — confirmed in
  `hass_client/sandbox_bridge.py`.
- **Phase 6 — two memory-exhaustion vectors:**
  - Context cache eviction on the resolve path: factored a single
    `_store_context()` helper used by both `_remember_context` and the miss path
    of `_resolve_context`, so `_CONTEXT_CACHE_MAX` + expiry-ordering apply
    uniformly. A flood of distinct unknown `context_id`s is now bounded.
  - Channel read backpressure (BOTH mirrors): `_dispatch` sheds over a
    `DEFAULT_MAX_QUEUED = 1024` cap on inflight handler tasks — inbound calls get
    a `ChannelOverloaded` error frame, pushes are dropped. Responses are always
    handled inline above the gate, so backpressure never starves a reply.
- **Phase 7 — adversarial tests** (one forged-frame test per gate; see below).
- **Phase 8 — doc reconciliation** (`ARCHITECTURE.md`). All gates shipped, so the
  malicious-sandbox guarantees were kept and each got a one-line "enforced on
  main in `bridge.py`/`channel.py`" note (§4 backpressure, §8 entity/service/
  event/context gates, §9 store quotas, §11 translation) plus a changelog row.
  **No "Known trust-boundary gaps" subsection** is needed — nothing was deferred.
  `README.md`/`CLAUDE.md` make no overstated boundary claims (only "isolated
  subprocesses", accurate), so no softening was needed.

## channel.py both-mirrors note

The Phase 6 read-backpressure edit is applied **byte-identically in the changed
region** to both hand-mirrored copies:

- `homeassistant/components/sandbox/channel.py`
- `sandbox/hass_client/hass_client/channel.py`

Verified with `diff` over the three changed regions (constant block, `__init__`
param/attr, `_dispatch` branch) — identical content (only file-wide line numbers
differ). It rebases on top of plan #1's `Channel.close()` fix and is a **separate
commit** (`85401a8`). The proto drift guard (`check_drift.sh`) only covers the
`_pb2` gencode, not `channel.py`, so the mirror identity is a manual discipline.

## Design decision: shed, don't block the reader (Phase 6 deviation)

The plan suggested "acquire the inflight semaphore before reading/dispatching the
next frame, so a slow handler throttles the reader." I implemented **load
shedding** (bounded inflight cap → reject calls / drop pushes) instead of
blocking the reader, because blocking the shared reader on the handler-concurrency
limit deadlocks the documented nested-call pattern: a handler that issues
`channel.call()` and awaits its reply needs that reply to come back through the
**same** reader. If all slots are held by such handlers and the reader is blocked
acquiring a slot for the next inbound frame, the awaited responses can never be
read → deadlock. This is real on the client mirror (a `call_service` handler doing
a `store_save` round-trip to main holds a slot while awaiting main's reply).
Shedding bounds memory without that liveness hazard and is safe in both mirrors;
responses are always dispatched inline (never shed), preserving liveness. The
generous default cap (1024) means honest fan-out never trips it. Documented in the
Phase 6 commit message and ARCHITECTURE §4.

## Adversarial tests added (Phase 7)

- `test_fire_event_forged_type_dropped` (parametrized: `homeassistant_stop`,
  `call_service`, `state_changed`, `zha_event`, `hue_event`) — none reach the bus.
- `test_register_service_unowned_domain_rejected` (`persistent_notification`).
- `test_register_entity_foreign_entry_rejected` (entry.sandbox = `other-group`).
- `test_register_entity_foreign_device_merge_rejected` (device_info colliding
  with a victim entry's device — merge refused, victim device untouched).
- `test_context_cache_bounded_under_id_flood` (cache ≤ `_CONTEXT_CACHE_MAX`).
- `test_store_rejects_overlong_key`, `test_store_rejects_oversized_value`
  (nothing hits disk).
- `test_foreign_returned_domain_is_dropped` (translation; forged `hue` discarded).
- `test_read_backpressure_sheds_over_queued_cap` (channel; over-cap calls get
  `ChannelOverloaded`, inflight set stops growing).

Existing tests updated to reflect the new gates (entries/domains tagged
`sandbox="built-in"` so they are *owned*): the shared `entry` fixtures in
`test_bridge.py`, `test_entity_query.py`, `test_domain_proxies.py`,
`test_crash_recovery.py`, `test_proto_transport.py`; the register_service tests in
`test_bridge.py`; and the schema test in `test_schema_and_unload.py`.
`make_channel_pair` gained `max_queued_a/b` passthrough.

## Final verification

```
# HA-core sandbox tests (1 deselected = pre-existing flake, see below)
$ uv run pytest tests/components/sandbox/ --no-cov -q -p no:randomly \
    --deselect '.../test_proto_transport.py::test_protobuf_codec_round_trip_is_byte_identical'
236 passed, 1 deselected, 2 warnings in 8.29s

# Client tests
$ uv run pytest sandbox/hass_client/ -q -p no:randomly
87 passed, 1 warning in 0.56s

# Proto drift guard
$ bash sandbox/proto/check_drift.sh
sandbox proto drift guard: gencode matches sandbox.proto.

# prek over the production files
ruff check / ruff format / codespell / prettier / mypy / pylint — all Passed
```

### Pre-existing flake (not caused by this plan)

`tests/components/sandbox/test_proto_transport.py::test_protobuf_codec_round_trip_is_byte_identical`
fails intermittently (~1 in N runs) in **full-file** mode, passing in isolation.
Cause: protobuf `Struct` map-field serialization order is implementation-defined,
so the `encode == re-encode` byte-identity assertion is order-sensitive to other
protobuf messages built earlier in the run. **Confirmed pre-existing**: the file
at `HEAD~8` (before any of this plan's commits) fails it identically (1–2
failures per run across 5 runs). This plan only touched an *unused* `entry`
fixture in that file. Fixing it (a `deterministic=True` serialize in the codec,
or relaxing the assertion) is out of scope for this trust-boundary plan — flagged
here for a future cleanup.

## Commits (local, on `sandbox`)

```
22af8b4 Phase 1 — main-side fire_event domain gate
3723fb9 Phase 2 — register_service ownership check
3139acb Phase 3 — entry/group ownership on register_entity
f55a43e Phase 4 — translation returned-domains gate
a12d74b Phase 5 — store server quotas
85401a8 Phase 6 — bound context-cache + channel-flood memory vectors
2738b8c Phase 7 — adversarial forged-frame tests per gate
51c8c06 Phase 8 — reconcile ARCHITECTURE security-posture docs
```
