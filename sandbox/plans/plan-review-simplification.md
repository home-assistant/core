# Plan — Simplification & cleanup (review follow-up #6)

> Source: 2026-06-12 sandbox code review, cleanup/altitude angle (all CONFIRMED).
> Status notes go to `sandbox/status/STATUS-plan-review-simplification.md`.
> **Do last** — it rebases cleanly over the bug-fix plans rather than fighting
> them. Quality only; no behaviour change except the explicitly-noted hot-path
> refactor (Phase 6), which is opt-in.

## Goal

Remove duplication, dead code, and boilerplate the review found, and add the
one missing drift guard. Each phase is independent; land them in any order
except Phase 1 (drift guard) which is most valuable first because it protects
every later hand-edit to the mirrored files.

## Success criteria

- [ ] The three hand-mirrored wire files have a drift guard like the `_pb2` one.
- [ ] Domain-proxy `supported_features` boilerplate collapses to one base hook.
- [ ] Dead `raise_not_proxied` and the no-op block are gone.
- [ ] `JsonCodec` is no longer the implicit production default.
- [ ] One JSON-coercion helper in the client package, not three.
- [ ] (Optional) the per-state-change task churn is replaced by a single writer.
- [ ] Both suites green; drift guard green; `uv run prek run` clean.

## Phase 1 — Drift guard for the mirrored channel/codec/messages

`channel.py`, `codec_protobuf.py`, `messages.py` are hand-maintained near-verbatim
copies in `homeassistant/components/sandbox/` and
`sandbox/hass_client/hass_client/` (~920 lines). codec + messages are
byte-identical; channel differs only in docstrings/log capitalization. The proto
`check_drift.sh` covers only the `_proto` gencode dirs — these three are
unprotected, exactly the drift class the proto guard exists to prevent.

- [ ] Extend `sandbox/proto/check_drift.sh` (or add a sibling
      `sandbox/proto/check_mirror_drift.sh`) to assert the two copies of
      `codec_protobuf.py` and `messages.py` are byte-identical, and that
      `channel.py` matches modulo the known docstring/log differences (normalize
      then diff, or make them truly identical and diff exactly).
- [ ] **Best:** make `channel.py` byte-identical too (move the cosmetic
      differences out), so the guard is a plain `diff`. Wire the guard into
      whatever runs `check_drift.sh` (pre-commit / CI).
- [ ] Document the "edit both mirrors" rule next to the guard (and remove the
      ad-hoc "apply to both" warnings the bug-fix plans had to carry).

## Phase 2 — Collapse the domain-proxy `supported_features` boilerplate

~17 of 31 domain proxies define a ~10-line `__init__` whose only post-`super()`
statement is
`self._attr_supported_features = <Domain>EntityFeature(description.supported_features or 0)`
(`light.py:44`, `fan.py`, `lock.py`, `cover.py`, `climate.py`, `media_player.py`,
`notify.py`, …).

- [ ] Add a class attribute hook on `SandboxProxyEntity`, e.g.
      `_features_flag: type[IntFlag] | None = None`, and have the base `__init__`
      (and the `sandbox_update_description` path, `entity/__init__.py:122-130`,
      which already does IntFlag-aware coercion) apply it once.
- [ ] Replace each domain's `__init__` override with a single
      `_features_flag = LightEntityFeature` line. Remove the now-empty overrides.
- [ ] Confirm the four `@final`-state mangled-attribute overrides (`button`,
      `event`, `notify`, `scene`) are untouched — they're a different special case.
- [ ] Run the domain-proxy tests to confirm features still type-wrap correctly.

## Phase 3 — Delete dead code

- [ ] Remove `raise_not_proxied` (`entity/__init__.py:30`) and its `__all__`
      entry (`:312`) — zero callers since the query RPCs landed. Drop the now-unused
      `NoReturn`/`HomeAssistantError` imports if nothing else uses them.
- [ ] Remove the vestigial no-op block at `entity_bridge.py:123-125`
      (`if old_state is not None and entity_id not in self._pending: … pass`).
      > If the client-bridge-fixes plan Phase 3 already restructured this block, skip — note in STATUS.

## Phase 4 — Stop defaulting the production `Channel` to `JsonCodec`

`Channel.__init__` defaults `codec` to `JsonCodec()` (`channel.py:346`);
`JsonCodec` ships in the production module and every real construction site
passes `ProtobufCodec` explicitly. A forgotten `codec=` silently speaks JSON and
fails at runtime against a protobuf peer.

- [ ] Make `codec` a **required** argument (or default to `ProtobufCodec`), so a
      missing codec fails at construction, not on the wire.
- [ ] Move `JsonCodec` to a test helper (e.g. under `testing/`) so it's not in
      the production import path; update the channel-core tests to import it from
      there. Apply across both mirrors.

## Phase 5 — One JSON-coercion helper in the client package

Three coercers exist in `sandbox/hass_client/hass_client/`:
`event_mirror._to_json_safe` (`:123`, raw set order),
`entity_bridge._serialise` (`:402`, sorted sets via `_iter`),
`entry_runner._json_safe` (`:201`, the clean `json_loads(json_bytes(...))`).
The two hand-rolled ones have already drifted on set ordering.

- [ ] Pick the `json_loads(json_bytes(...))` approach (HA-aware encoder, single
      source of truth) and expose it as one shared helper; replace the two
      hand-rolled coercers with it.
- [ ] Confirm the unified behaviour for sets/enums/dataclasses matches what each
      call site needs (state attrs, event data, service responses); add a small
      round-trip test for the consolidated helper.

## Phase 6 — (Optional) single writer task on the hot path

`entity_bridge` spawns an `asyncio.create_task` per state change to await one
`channel.push` behind the write lock (`entity_bridge.py:100`). On a polling
integration with hundreds of sensors this is per-event task + f-string churn,
and state ordering rests implicitly on task-creation order + lock FIFO.

- [ ] Replace with a single long-lived writer task draining an `asyncio.Queue`
      (the recorder pattern): `_on_state_changed` enqueues; one task awaits
      `channel.push` sequentially. Ordering becomes explicit (queue order).
- [ ] Fold in the client-bridge-fixes plan Phase 3's "flush current state after register" so the queue
      is the single place push ordering is reasoned about. **Coordinate with the
      client-bridge-fixes plan** — if it already restructured this path, build on it; if this lands
      first, the client-bridge-fixes plan implements its flush on the queue.
- [ ] Bound the queue (drop-oldest or backpressure) so a wedged channel can't grow
      it unboundedly — mirrors the trust-boundary plan's backpressure principle.
- [ ] Gate on effort: this is the one phase that changes runtime behaviour; if the
      iteration is tight, ship Phases 1–5 and defer Phase 6.

## Verification

```bash
bash sandbox/proto/check_drift.sh           # + the new mirror guard
uv run pytest tests/components/sandbox/ --no-cov -q
uv run pytest sandbox/hass_client/ -q
uv run prek run --files <changed>
```

## Risks / open questions

1. **Sequence after the bug plans.** Phases 3 & 6 touch `entity_bridge.py`, which
   the client-bridge-fixes plan also edits. Land the client-bridge-fixes plan first; this plan rebases. The INDEX records the
   order.
2. **Drift guard scope** (Phase 1): making `channel.py` byte-identical may pull a
   few log strings into a shared form — confirm logs still read sensibly on both
   sides. A normalize-then-diff guard is the fallback if exact identity is
   undesirable.
3. **Features hook coverage** (Phase 2): a couple of domains may index
   `supported_features` differently; spot-check each converted file's tests. Keep
   the base hook opt-in (`_features_flag = None` → no-op) so unconverted/odd
   domains are unaffected.
4. **Phase 6 ordering guarantees**: the queue must preserve per-entity ordering
   (it does, FIFO) — but confirm no consumer relies on cross-entity ordering that
   task-scheduling happened to provide.

## Out of scope

- Behavioural bug fixes (plans 2–5) — this plan is quality only, except the
  opt-in Phase 6 refactor.
- Coalescing same-tick service calls into one multi-entity RPC (a separate noted
  future optimisation, not a review finding).
