# STATUS — plan-review-simplification (review follow-up #5, the last)

Quality/cleanup plan that rebased over the four bug-fix plans (crash-recovery,
trust-boundary, client-bridge-fixes, flow-fidelity). Phases 1–5 shipped;
Phase 6 evaluated and **deferred** (the one behaviour-changing, optional phase).
Both suites green, both drift guards green, `uv run prek` clean.

## Phase 1 — Drift guard for the mirrored channel/codec/messages ✅

- **`channel.py` made byte-identical** across both mirrors (the BEST option, so
  the guard is a plain `diff`, not normalize-then-diff). `codec_protobuf.py` and
  `messages.py` were already byte-identical. The only differences in `channel.py`
  were cosmetic — module docstring, a few comments, "peer"/"main" wording, log
  capitalization, and some HA-only inline comments; there were **no code
  differences**. Reconciled by taking the richer HA-side content as canonical
  (the docstring's symmetric "either side may call" wording reads sensibly on
  both sides) and copying it verbatim to the client mirror.
- Added an in-file mirror-notice comment (identical on both copies) right after
  the `channel.py` docstring documenting the edit-both rule, and extended the
  `codec_protobuf.py` / `messages.py` docstrings to reference the guard.
- **New guard:** `sandbox/proto/check_mirror_drift.sh` — a plain `diff` of all
  three pairs (no external tooling). Wired into `.pre-commit-config.yaml` as a
  **regular** hook (`id: sandbox-mirror-drift`) that fires whenever either copy
  of a mirrored file changes (`files:` regex matches both directories). Chosen
  as a regular hook (vs the proto guard's manual stage) because it needs no
  `uv`/protoc bootstrap, so it can actively block drift on every commit.
- This retires the ad-hoc "apply to both mirrors" discipline the earlier plans
  carried by hand.

## Phase 2 — Collapse domain-proxy `supported_features` boilerplate ✅

- Added `_features_flag: type[IntFlag] | None = None` class-attr hook + a
  `_coerce_supported_features` helper on `SandboxProxyEntity`, used by **both**
  `__init__` and `sandbox_update_description` (the latter previously did its own
  `isinstance(current, IntFlag)` coercion — now uses the class attr directly).
- Replaced **17** identical ~10-line `__init__` overrides (light, fan, lock,
  cover, climate, media_player, notify, update, vacuum, lawn_mower, remote,
  valve, alarm_control_panel, weather, water_heater, humidifier, siren) with a
  single `_features_flag = <Domain>EntityFeature` line each. Dropped the
  now-orphaned `TYPE_CHECKING` imports of `SandboxBridge`/`SandboxEntityDescription`.
- The four `@final` mangled-attribute **`sandbox_apply_state`** overrides
  (button, event, notify, scene) are untouched — a different special case.
  `notify` had both an `__init__` (converted) and a `sandbox_apply_state`
  (kept).

## Phase 3 — Delete dead code ✅

- Removed `raise_not_proxied` (zero real callers since the query RPCs landed),
  its `__all__` entry, and the now-unused `NoReturn` / `HomeAssistantError`
  imports from `entity/__init__.py`.
- **No-op block NOT already gone** — the brief anticipated plan 3 might have
  removed it, but plan 3 restructured `_register_and_push` (the reconcile flush)
  and **left** the vestigial `if old_state is not None and entity_id not in
  self._pending: pass` block in `_on_state_changed`. Removed it (control fell
  through it unchanged) plus the now-dead `old_state` assignment. The module
  docstring's `(old_state is None)` parenthetical describes HA's event semantics
  for first appearances (not this function's implementation), so it was left
  untouched.

## Phase 4 — Stop defaulting the production `Channel` to `JsonCodec` ✅

- `Channel.__init__` / `from_transport` now take **`codec` as a required**
  keyword (chosen over "default to ProtobufCodec", which would create a
  `channel.py` → `codec_protobuf.py` circular import). Every production site
  already passes `codec=ProtobufCodec()`; a forgotten codec is now a
  construction-time error instead of a silent JSON-vs-protobuf wire mismatch.
- **`JsonCodec` relocated** out of the production `channel.py` (both mirrors,
  kept byte-identical) to each side's test helpers:
  - HA: `tests/components/sandbox/_helpers.py` (already the channel-core test
    helper; `test_channel.py` imports it from there).
  - Client: `hass_client/testing/_jsoncodec.py` (the established importable
    test-support package; `tests/test_sandbox_bridge.py` imports it from there).
- Dropped the now-unused `import json` from `channel.py`; updated the
  `protocol.py` docstring (required codec + relocated JSON codec). Fixed two
  channel-core tests that built channels via `from_transport` without a codec
  (relied on the removed default) to pass `codec=JsonCodec()`.

## Phase 5 — One JSON-coercion helper in the client package ✅

- New `hass_client/_json.py` exposing **`json_safe`** — built on HA's
  `json_encoder_default` (the `as_dict`/set/enum/datetime-aware single source of
  truth, mirroring `json_bytes` incl. `OPT_NON_STR_KEYS`) **plus a `str(obj)`
  fallback** for unknown objects.
- Replaced all three drifted coercers with it:
  - `event_mirror._to_json_safe` (raw set order) — **removed**. The `str()`
    fallback is preserved in the shared helper because `_to_json_safe` ran in an
    unguarded sync `@callback`; without it, an arbitrary domain object in
    best-effort event data would raise in the bus callback and drop the event.
  - `entity_bridge._serialise` + `_iter` (sorted sets) — **removed**. Set order
    becomes raw `list(set)`; the capabilities hash is compared **within one
    process**, where equal sets iterate identically, so within-process hash
    stability (the resend guard) is preserved without sorting. Dropped the
    now-unused `Iterable` import.
  - `entry_runner._json_safe` — kept as a thin wrapper (its empty-result `{}`
    guard + `-> dict` contract) delegating to `json_safe`; dropped the now-unused
    `json_bytes` / `json_loads` imports.
- **Test added:** `sandbox/hass_client/tests/test_json.py` — round-trips sets,
  enums, `as_dict` objects, datetimes, the `str()` fallback, non-str keys, and a
  plain-payload identity case (7 tests).

## Phase 6 — (Optional) single writer task on the hot path ⏸️ DEFERRED

Evaluated in depth and **deferred** per the brief's explicit effort gate ("if it
risks the green suite, SHIP Phases 1–5 and DEFER Phase 6 … do not leave the
suite red chasing it").

A *clean* single-writer queue cannot be a simple swap of the per-state-change
`create_task`: to be the single place push ordering is reasoned about (the
plan's goal) it must subsume the register **call** (request/response), state
pushes, unregister, resend, the `_pending`/`_removed_while_pending` race
handling, **and** plan 3's post-register flush — while (a) preserving per-entity
FIFO without serializing every entity behind one entity's register-RPC
round-trip, (b) staying bounded with drop-oldest/backpressure, and (c) keeping
clean shutdown (the current `drain_inflight` operates on the channel's inflight
handler tasks, not these bridge-side tasks; a long-lived writer changes that).
A partial version that queued only the registered-entity state pushes would
split push-ordering between the queue and the still-direct register/flush/
unregister awaits — reintroducing the exact cross-path ordering ambiguity the
phase exists to remove, so it would not be "clean."

This is the one phase the plan flags as runtime-behaviour-changing, and the
in-code handoff note (`entity_bridge.py` `_register_and_push`) already frames it
as a substantial follow-up. **Plan 3's post-register flush remains in place**
(`entity_bridge.py:176-209`, handoff NOTE intact) and the suite stays green.

## Verification (all green)

```
$ bash sandbox/proto/check_mirror_drift.sh
sandbox mirror drift guard: all mirrored wire modules match.

$ bash sandbox/proto/check_drift.sh
sandbox proto drift guard: gencode matches sandbox.proto.

$ uv run pytest tests/components/sandbox/ --no-cov -q -p no:randomly
245 passed, 2 warnings in 8.32s

$ uv run pytest sandbox/hass_client/ -q -p no:randomly
111 passed, 1 warning in 0.59s
```

`uv run prek run --files <changed>` clean for every commit. Note on the known
pre-existing flake: `test_proto_transport.py::test_protobuf_codec_round_trip_is_byte_identical`
failed once in a random-order full-file run (process-global protobuf Struct
map-ordering non-determinism) and passed in isolation and on re-run — not caused
by these changes, which don't touch the serialization path.

## Commits

- `81f92e770c7` Phase 1 — drift guard for hand-mirrored wire modules
- `303433a4e63` Phase 2 — collapse domain-proxy supported_features boilerplate
- `c07c917b52b` Phase 3 — delete dead code (raise_not_proxied + no-op block)
- `ceff3507316` Phase 4 — make Channel codec required, move JsonCodec to tests
- `839a870b5df` Phase 5 — consolidate client JSON coercers into one helper
- (this STATUS commit) — landing note
