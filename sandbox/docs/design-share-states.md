# Sync-states design (post-v2)

> **Status:** design only. Phase 7 wired the scoped sandbox token and a
> per-group `share_*` config; Phase 20 deleted that config because
> nothing consumed it. This doc captures the shape we want before
> someone picks the consumer up.

## Goal

Sandboxed integrations should be able to react to entity-state changes
that originated in **main** (or, eventually, in other sandboxes), so
automation-, script-, and template-style logic written *inside* a
sandbox behaves the same as if it ran in main. Equivalently: a
sandboxed integration that calls `hass.states.async_all()` should
optionally see the same view of the world a non-sandboxed integration
sees.

v1 sandbox gave the sandbox the system user's full access token and
therefore unconditional read access to all of main's data. Phase 7
locked v2 down by default — the sandbox sees only its own
entities/services/events. The locked-down posture is the right
default; we just owe a controlled opt-in.

## Key constraint: entity_id alignment

Without explicit alignment, the sandbox's own `EntityRegistry`
generates entity_ids independently. A sandbox-side automation written
against `light.kitchen` would silently target a *different*
`light.kitchen` from the one main hosts under the same slug, because
the two registries pick suggested_object_ids independently.

The fix: shared entities **must use main's entity_id** when projected
into the sandbox's state machine, regardless of what the sandbox's
local registry would have chosen.

Mechanism:

- Main's entity_registry is mirrored into the sandbox as a read-only
  view (initial snapshot + delta stream).
- `entity_id` is the canonical name on both sides. The mirror writes
  registry rows verbatim — the sandbox does not run its own
  collision/suggest logic against mirrored rows.
- Sandbox-side state writes for **sandbox-owned** entities still flow
  through the existing entity bridge (Phase 5). The bridge already
  maps sandbox-local `entity_id` → main's `entity_id` via
  `SandboxBridge._entities` so there is no conflict between the
  sandbox-owned and main-owned naming.

## Mechanism sketch

1. The sandbox opens a websocket back to main. The auth token is the
   scoped `RefreshToken` from Phase 7 — same scope set
   (`{"sandbox/", "auth/current_user"}`) plus a single new exact
   entry `share/subscribe` (added to
   `homeassistant/components/sandbox/auth.py::SANDBOX_TOKEN_SCOPES`).
2. The sandbox calls three subscribe commands, one per data class:
   - `share/subscribe_states` — initial snapshot of every state main
     wants this sandbox to see + `state_changed` deltas.
   - `share/subscribe_entity_registry` — initial snapshot of every
     registry row this sandbox is allowed to see + create/update/remove
     deltas.
   - `share/subscribe_areas` — initial snapshot of every area + delta
     stream. Area registry is small; full snapshot is fine.
3. Each subscribe response carries a subscription id; subsequent push
   frames carry that id so the sandbox can route to the right
   consumer.
4. On the sandbox side, each consumer applies the delta locally:
   - States → `hass.states.async_set(entity_id, state, attributes, …)`
     (with the existing source-context plumbing to mark these as
     remote).
   - Entity registry → `er.async_update_entity` / `async_get_or_create`
     / `async_remove` on the sandbox's `EntityRegistry`. The sandbox
     marks mirrored rows with a `source` field so its own
     `async_remove` calls against them return an error rather than
     mutating main's data.
   - Areas → same pattern against `AreaRegistry`.

The control channel is the existing `Channel` for everything inbound
from main → sandbox; subscription frames ride that channel rather than
opening a second connection.

## Filtering on main's send-side

Per-sandbox allow-list, configured at sandbox-startup time. Coarse
grain is fine for v3 — entity-domain-level allow-listing covers the
main use cases (`["light.*", "sensor.*"]`, etc.). Filtering happens
**before** the push hits the wire so a state-change-heavy main does
not fan out N copies of every event to every sandbox.

Defaults match the Phase 7 plan that Phase 20 deleted:

| Group | states / entity_registry / areas |
|---|---|
| `built-in` | all on |
| `main` | all on |
| `custom` | all off |

The defaults are a starting point; the per-sandbox allow-list (set by
the integration's config, not by the framework) can narrow them
further. Default-on for `built-in` matches v1's behaviour so existing
integrations behave the same; default-off for `custom` keeps the
trust boundary tight for untrusted integrations.

## Open questions

- **Direction.** Is the share one-way (sandbox sees main only) or
  bidirectional (sandboxes also see each other's states)? Latter
  routes through main — main's entity_registry/state machine already
  carries the sandbox-owned entities via the existing bridge, so a
  second sandbox subscribing to `share/subscribe_states` would see
  them transparently. The cost is one extra hop per state change. Lean
  one-way for v3 and add bidirectional only if a real integration
  needs it.
- **Mirrored registries: write-through behaviour.** What happens if a
  sandbox calls `er.async_remove(entity_id)` for a main-owned entity?
  Cleanest answer: read-only mirror — the call returns an error and
  the row stays. Alternative: silently no-op. The error path is
  louder and makes the boundary explicit, so prefer it.
- **Device + area registries.** Same pattern as state +
  entity_registry. Phase 19's `device_registry` bridging (sandbox →
  main) is the precursor; the reverse direction (main → sandbox) is
  this work.
- **Performance.** A state-change-heavy main fans out to every
  sandbox subscribed to the matching domain. Per-event filtering on
  main's send-side is the cheap fix (already a non-goal to fan out
  unfiltered); a domain-indexed subscription map on main avoids the
  per-event filter walk for sandboxes with narrow allow-lists.

## Non-goals

- **Full read-write registry mirroring.** Sandboxes cannot write to
  main's entity_registry / area_registry / device_registry through the
  share channel. The existing entity bridge handles
  sandbox-owned-entity creation; the share channel is read-only into
  the sandbox.
- **Bidirectional device targeting via the share channel.** A
  sandbox-side automation calling a main-side service (e.g.
  `light.turn_on` against a main-owned light) already works via the
  existing service mirror — the share channel does not need to grow
  that surface.
- **Frontend surfacing of the per-sandbox allow-list.** The knob is
  a backend/integration config; no UI in v3.

## Why now

Phase 7 added `SandboxGroupConfig` + `SharingConfig` + `--share-*`
CLI flags + `DEFAULT_GROUP_CONFIGS`. Phase 20 deleted all of it
because nothing consumed it; carrying unwired flags risks readers
assuming functionality that isn't there. This doc replaces the dead
surface as the single point of truth for the eventual consumer.

The locked-down posture from Phase 7 stays — defaults remain
everything-off. The opt-in subscription consumer lands behind the
new config surface (whatever shape it takes when implemented) so the
default behaviour does not regress.

## Files this design will touch

```
homeassistant/components/sandbox/auth.py           (extend SANDBOX_TOKEN_SCOPES)
homeassistant/components/sandbox/share.py          (new — main-side share/subscribe_* handlers, send-side filter)
homeassistant/components/sandbox/manager.py        (re-introduce a per-sandbox allow-list)
sandbox/hass_client/hass_client/share.py           (new — sandbox-side subscription consumer)
sandbox/hass_client/hass_client/sandbox.py         (open the websocket back to main; wire the consumer)
```

Core HA: no further changes expected — Phase 7's `RefreshToken.scopes`
and `_scope_allows` cover the auth side; the websocket subscription
protocol is already public.
