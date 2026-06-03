# Sandbox v2 — What's changed (broadcast draft)

> **STATUS: DRAFT.** Finalized in the batch-closing step (Phase E) once all
> pending phases land. Each item is tagged with its source plan + a checkbox so
> this doubles as a landing tracker. When a phase ships, confirm/trim its entry
> and check it off. Audience-first so readers find their part fast.
>
> Intended home when finalized: `sandbox_v2/CHANGES.md` (or wherever you
> broadcast from). Keep it short — link to OVERVIEW.md for depth.

## TL;DR
- Store IO is now routed via a `current_sandbox` **ContextVar** in core HA,
  replacing the module-level monkey-patch of
  `homeassistant.helpers.storage.Store`. Same primitive will later carry
  cross-sandbox IR/RF/BLE calls.
- Phase 7's `RefreshToken.scopes` mechanism was **reverted from core HA** —
  no consumer shipped, so it was dead weight. The sandbox token is now a
  plain system-user token. Re-introduce when the sandbox→main websocket
  actually lands.
- The `built-in` sandbox group is now locked down like `custom` (HACS) — no
  access to other integrations' states/registry/areas. ~18 helper/aggregator
  integrations consequently run on **main**.
- Sandboxes are now **stateless**: they fetch custom (HACS) integration code at
  startup from a git URL+sha pushed by main; storage already routes to main.
- The wire protocol moved to **protobuf** over **pluggable transports**
  (stdio + unix socket; websocket later).
- Config-flow forms, entity updates, and validation errors now round-trip
  faithfully across the sandbox boundary.
- **Sandbox v1 has been removed.**

## ⚠️ Breaking changes
- [x] **v1 removed** — `homeassistant/components/sandbox/` + the v1 client are
  gone. Use v2. (`plan-v1-removal.md`, done 2026-05-28)
- [ ] **`RefreshToken.scopes` field + dispatcher enforcement removed from core
  HA.** Phase 7's scope mechanism was reverted; no consumer shipped while it
  was in tree. Existing auth stores with `scopes` keys on refresh tokens load
  silently (the field is dropped on read). Re-introduces when the sandbox→main
  WS transport lands and needs scoping. (`plan-strip-auth-scopes.md`)
- [ ] **`install_remote_store` monkey-patch removed.** Sandbox Store IO now
  routes via a `current_sandbox` ContextVar in `homeassistant/helpers/`. No
  user-visible API change; internal-only. (`plan-sandbox-context.md`)
- [ ] **Runtime CLI flag `--group` → `--name`** on
  `python -m hass_client.sandbox_v2`. (`plan-fidelity-batch.md` #2)
- [ ] **`built-in` group locked down** — these integrations now run on **main**,
  not in a sandbox (they read data they don't own): `template`, `group`,
  `homekit`, `min_max`, `statistics`, `trend`, `threshold`, `derivative`,
  `integration`, `utility_meter`, `filter`, `mold_indicator`, `bayesian`,
  `generic_thermostat`, `generic_hygrostat`, `switch_as_x`, `history_stats`,
  `proximity`. (`research/builtin-lockdown-breakage.md`, point 1)
- [ ] **Proxy entity unique_ids are now prefixed with the source integration
  domain** (`<domain>:<unique_id>`) to avoid collisions across integrations in a
  group. Pre-release → no migration. (`plan-fidelity-batch.md` #5)

## For integration authors
- [ ] **Custom (HACS) integrations are fetched at startup.** Main pushes the git
  URL + pinned commit sha; the sandbox clones it before setup. No persistent
  code on disk → sandboxes are wipe-and-restart safe. (`plan-ephemeral-sources.md`)
- [ ] **Config-flow forms render faithfully.** Selectors and sections now
  survive the sandbox round-trip (previously some collapsed to plain inputs).
  (`plan-fidelity-batch.md` #4)
- [ ] **Entity & device info updates propagate.** Changing an entity's name,
  icon, capabilities, or device info after setup now reflects on main (the
  registration is idempotent + watches registry-updated events). (`plan-fidelity-batch.md` #6)
- [ ] **Validation errors keep their shape.** A `vol.Invalid` raised by a
  sandboxed service handler now surfaces on main as a real `vol.Invalid` with
  its `.path`, instead of a flattened `TypeError`. (`plan-fidelity-batch.md` #7)
- [ ] If your integration genuinely needs other integrations' state under
  lockdown, it must run on main (see the breaking-changes list) — a scoped
  opt-in is future work (`docs/design-share-states.md`).

## For sandbox / core contributors
- [ ] **Protobuf wire format.** Messages are protobuf (`Frame` envelope + typed
  per-message bodies; `Struct`/`ListValue` only for voluptuous schemas and
  `service_data`). `.proto` source + generated `_pb2` checked in; regen script
  provided. (`plan-transport.md`)
- [ ] **Pluggable transports.** stdio + unix socket now; the `Transport` seam
  accepts the deferred websocket drop-in (lands with share-states).
  (`plan-transport.md`)
- [ ] **Handlers consume typed protobuf messages** (no dict adapters).
- [ ] **Test Dockerfile** for running the client runtime against main.
  (`plan-docker.md`)
- [ ] v1 reference code lives only in git history now.

## Not in this batch (so people don't ask)
- Websocket transport (deferred to the share-states connection work).
- The scoped state-sharing opt-in consumer (`docs/design-share-states.md`).
- `calendar`/`todo`/`weather` query-shaped RPCs; non-idempotent service
  handlers (`ai_task`, `image`).
