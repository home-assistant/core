# Home Assistant Sandbox — Architecture

> This document describes the **final, current architecture** of the Home
> Assistant sandbox: how an integration runs in an isolated subprocess while
> the main instance keeps a single unified view of devices, entities,
> services, and events. It is a state-of-the-system reference, not a history.
> A condensed changelog of the work that produced this state is at the bottom.
>
> The design rationale for individual decisions is in [`docs/`](docs/); a quick
> file map is in [§15](#15-where-to-look-in-the-code).

## 1. Goal

Run a Home Assistant integration's setup, config flow, entities, services,
events, and storage fully inside an **isolated subprocess** ("sandbox"), while
the main HA instance presents a **single, unified view** that looks identical to
running everything locally.

A user who adds a light integration through the frontend ends up with a device
plus entities in main's registries, working area targeting (`light.turn_on`
against an area resolves the sandboxed lights like any other light), and the
integration's services, events, and translations available on main — with the
integration code only ever executing inside the sandbox.

The sandbox is **stateless**: it holds no persistent state of its own. Its
storage and restore-state route to main (§9), and even the integration's *code*
is fetched at startup (§7) rather than living on the sandbox — so a sandbox is
wipe-and-restart safe and could run anywhere, including a fresh container.

## 2. Components

### Main side — `homeassistant/components/sandbox/`

| Component | Responsibility |
|---|---|
| `SandboxFlowRouter` | Plugged into `hass.config_entries.router`; routes new flows and entry setup/unload to a sandbox or to main. |
| `SandboxManager` | `dict[group → SandboxProcess]`; lazily spawns one subprocess per group, supervises it, restarts on crash. |
| `SandboxBridge` (per group) | Owns the proxy-entity registry, forwards entity service calls, re-fires sandbox events, and runs the per-group store server. |
| `classifier.py` | Pure function `Integration → SandboxAssignment` deciding which group (or main) an integration belongs to. |
| `sources.py` | The integration-source resolver registry (how custom code is located). |
| `translation.py` | `SandboxTranslationProvider` — pulls a sandboxed integration's translation strings from the live sandbox into main's translation cache (see §11). |
| `catalog.py` | Re-exports the loader catalog hook so HACS can make a sandbox-only custom integration discoverable + named in the add-integration picker (see §11). |

### Sandbox side — `sandbox/hass_client/`

The subprocess runs a private `HomeAssistant` instance hosting:

| Component | Responsibility |
|---|---|
| `SandboxRuntime` | Owns the private hass, opens the control channel, sets the store-routing contextvar. |
| `FlowRunner` | Drives the integration's real `ConfigFlow` on flow_init / step / abort. |
| `EntryRunner` | Fetches integration code if needed, then runs `async_setup_entry` against the private hass. |
| `EntityBridge` | Pushes `register_entity` + `state_changed` to main. |
| `ServiceMirror` | Pushes `register_service` for approved domains. |
| `EventMirror` | Re-fires `<approved_domain>_*` events to main. |
| `ApprovedDomains` | Refcounted domain set that gates the service/event mirrors. |
| `ChannelSandboxBridge` | Implements store load/save/remove over the channel (see §8). |

## 3. Routing

`classify(integration)` is a pure function run from the router **at flow
creation** (`async_create_flow`). At entry setup the router reads the routing
tag already persisted on `ConfigEntry.sandbox` rather than re-classifying — an
entry with no `sandbox` value simply runs on main. `classify` uses
`Integration.platforms_exists()` so it never imports the integration to make the
call. First match wins:

1. `integration_type == "system"` → **main** (part of the HA runtime; sandboxing is meaningless).
2. `domain ∈ ALWAYS_MAIN` → **main** (hand-picked deny-list, each with an inline "why").
3. Any platform in `SANDBOX_INCOMPATIBLE_PLATFORMS` → **main** (`stt`, `tts`, `conversation`, `assist_satellite`, `wake_word`, `camera` — audio/byte streams the channel can't ferry; plus `todo`, whose To-do panel reads the sync `todo_items` property that also feeds `state`, so it needs a pushed item-list cache the bridge doesn't have yet — see [`docs/query-shaped-rpcs.md`](docs/query-shaped-rpcs.md)).
4. Custom (non-built-in) integration → group **`custom`**.
5. Otherwise → group **`built-in`**.

**`ALWAYS_MAIN`** holds two classes of integration. *Behavioural punts*:
`script`, `automation`, `scene`, `cloud`, `ai_task`, `image` (the last two do
non-idempotent pre-dispatch work no bridge intercepts cleanly). *Lockdown
helpers* — integrations that read entities/registries/areas they don't own, so
they cannot function under the locked-down sandbox posture and run on main:
`template`, `group`, `homekit`, `min_max`, `statistics`, `trend`, `threshold`,
`derivative`, `integration`, `utility_meter`, `filter`, `mold_indicator`,
`bayesian`, `generic_thermostat`, `generic_hygrostat`, `switch_as_x`,
`history_stats`, `proximity`. A future scoped state-sharing opt-in
([`docs/design-share-states.md`](docs/design-share-states.md)) could return the
helper cluster to sandboxes.

Three groups ship by default: **`main`** (hosts no process — anything routed to
main runs directly), **`built-in`** (every other built-in integration), and
**`custom`** (every HACS / user integration). The routing tag is persisted on
the first-class `ConfigEntry.sandbox` field, not in `entry.data`.

## 4. Control channel & transport

Main and sandbox talk over a **`Channel`** with a deliberate three-layer split,
so each layer is independently testable and replaceable:

```
Channel  (dispatch core: id↔reply map, inflight concurrency, register/call/push)
  → Codec        (Frame ↔ bytes; ProtobufCodec in production, JsonCodec for channel-core tests)
    → Transport  (StreamTransport: 4-byte big-endian length-prefix framing over a byte pipe)
```

- **Wire format is protobuf.** A `Frame` envelope carries `id`, `type`, and a
  `oneof body { request | response }`; each `type` maps to a typed request
  message and a typed result message. The codec — not the channel — owns the
  `type → (request_cls, result_cls)` registry, keeping the concurrency-critical
  dispatch core codec-agnostic. The `.proto` is the single source of truth;
  generated `_pb2` modules are checked into both mirrors, regenerated by
  `proto/generate.sh` (isolated venv, no project-venv pollution) and guarded by
  a drift check. Genuinely **dynamic payloads** (service data, state
  attributes, store envelopes, flow dicts, serialized schemas) cross as
  orjson-encoded JSON in `bytes` fields — measured ~13x faster than the
  `google.protobuf.Struct` fields they replaced, with native number fidelity
  (no more double-only Struct numbers) and a single coercing encoder
  (`messages.encode_json`) on both sides; typed scalars stay proto-typed
  fields.
- **Transports are pluggable.** `stdio://` (default — frames ride the
  subprocess stdin/stdout) and `unix://<path>` (opt-in,
  `SandboxManager(transport="unix")`; main is the unix server, the runtime
  dials back) both reuse `StreamTransport`'s length-prefix framing. `ws://` is
  reserved and rejected with `NotImplementedError`; the `Transport` seam
  accepts a future `WebSocketTransport` drop-in without touching the channel.
- **Handshake.** The runtime sends a `Ready` frame (`sandbox/ready`) as its
  first message; the manager treats its arrival as "running". stdout carries
  nothing but channel frames (no text marker; logs go to stderr).

Concurrency is real: handlers run as independent tasks bounded by an inflight
semaphore, so a slow handler can't head-of-line-block the channel. A second
bound caps the **total** inflight handler tasks (running + queued): under a
frame-flood from a compromised peer the dispatch layer sheds — inbound calls are
rejected with a `ChannelOverloaded` error frame and pushes dropped — rather than
growing unbounded decoded payloads (each up to the 16 MB frame cap); responses
are always handled inline so backpressure never starves a reply. Enforced
identically in both `channel.py` mirrors (`_dispatch`); the per-frame size cap is
the other half of the channel's memory bound.

## 5. Lifecycle

**Spawn** is lazy — `SandboxManager.ensure_started(group)` starts the
subprocess only when the first flow or entry routes to it:

```
python -m hass_client.sandbox --name <group> --url stdio://
```

**Crash recovery** is bounded: `SandboxProcess` restarts on unexpected exit up
to 3 times in a 60s sliding window with backoff; exceeding the budget marks the
sandbox `failed`, `ensure_started` raises `SandboxFailedError`, and the router
marks affected entries `SETUP_ERROR`. A `ChannelClosedError` *during* an
`entry_setup` round-trip (the sandbox crashed mid-setup) is also reported as
`SETUP_ERROR` — the entry stays recoverable via a manual reload. The router
runs *outside* `ConfigEntry.async_setup`, so it cannot reach core's
`SETUP_RETRY` timer (`async_call_later`); setting `SETUP_RETRY` from the router
would wedge the entry in a retry state that never fires. A router-driven true
retry is a follow-up.

When a crashed sandbox respawns, the manager's `on_ready` hook fires once the
fresh process is up: the displaced bridge is torn down (its proxy entities +
`EntityComponent` platform slots released through the public
`async_unregister_remote_platform` hook) and the group's still-`LOADED` entries
are re-driven through `async_schedule_reload`, so every entity re-registers
against the new bridge. While the sandbox is down its proxies are flipped
unavailable (via `on_channel_closed`) rather than serving stale state.

**Graceful shutdown** on `EVENT_HOMEASSISTANT_STOP`: the manager fans out
`sandbox/shutdown`; each sandbox unloads its entries, snapshots
`RestoreEntity` state into the reply, and schedules its own exit; main persists
the returned `restore_state` to `<config>/.storage/sandbox/<group>/`. SIGTERM →
SIGKILL backstops any sandbox that didn't ack. On the next boot the runtime
warm-loads `core.restore_state` before any handler registers, so the first
`RestoreEntity.async_get_last_state()` sees the previous run's state.

## 6. Config-flow forwarding

HA Core's `ConfigEntries` grows a single `router` attribute consulted at three
sites: `async_create_flow` (new flow), `async_setup` (existing entry), and
`async_unload` (entry teardown).

For a sandboxed handler the router returns a `SandboxFlowProxy` `ConfigFlow`
that issues `sandbox/flow_init` / `flow_step` / `flow_abort` RPCs and re-issues
each marshalled `FlowResult` as native `async_show_form` /
`async_create_entry` / `async_abort`. Inside the sandbox the integration's real
`ConfigFlow` runs in a `_SandboxFlowManager` that short-circuits CREATE_ENTRY —
**main is the canonical owner of the `ConfigEntry`**.

**Main alone decides the group, and the sandbox never controls how its data is
stored or routed.** The group is computed by main's `classify()` and passed to
the proxy's constructor; on the final `create_entry`, the main-side proxy sets
`create_result["sandbox"]` to *its own* (main-determined) group, overwriting
anything in the sandbox's reply — and the wire `FlowResult` has no group/sandbox
field for the sandbox to populate in the first place. The framework reads that
main-set value into `ConfigEntry.sandbox`, and the next `async_setup`
round-trips an `entry_setup` RPC. A compromised sandbox can shape its own
flow's forms and validation, but it cannot influence which group it lands in,
where its entry is persisted, or any other main-side storage/routing decision.

`data_schema` round-trips losslessly: it serialises via `voluptuous_serialize`
and the main side rebuilds the **real** `Selector` / `data_entry_flow.section`
objects, so when the flow manager re-serialises for the frontend the original
list is reproduced verbatim — selectors keep their widgets instead of degrading
to plain text boxes. The sandbox flow's `unique_id` rides every result so main's
duplicate-detection fires.

## 7. Statelessness — integration source fetched at startup

A sandbox holds no persistent state. Config arrives on `entry_setup`,
storage/restore-state routes to main (§8), and the last stateful bit — the
**integration code itself** — is fetched at startup. `EntrySetup` carries a
typed `IntegrationSource`:

- `{kind: "builtin"}` — the bundled `homeassistant` package provides it; no-op.
- `{kind: "git", url, ref, tag, domain, subdir}` — `ref` is an **exact commit
  sha** (never a moving tag), so the fetched tree can't be re-pointed between
  resolution and fetch.

**Main** stays HACS-agnostic via a registered resolver hook:
`async_register_sandbox_source_resolver(hass, resolver)` lets HACS (or anything)
map a custom domain → git source. Built-ins short-circuit via
`Integration.is_built_in`; a custom integration with no resolver **raises**
rather than silently falling back. The resolver pins the version to a sha
(core performs no network I/O; `tag` is logs-only).

**Sandbox** runs `async_ensure_integration_source` before `async_setup`: a git
source downloads GitHub's codeload tarball for the exact sha (no `git` binary
dependency) and extracts the repo's `subdir` into
`<config>/custom_components/<domain>`, verifying a `manifest.json` is present. A
process-lifetime cache keyed by `(url, ref)` fetches each repo once; nothing
survives a restart, keeping the sandbox wipe-and-restart safe. The download
primitive is injected so tests never hit the network.

> **Known runtime gap:** custom integrations that ship Python dependencies need
> `async_process_requirements` (pip) plus network egress (GitHub + PyPI) at
> setup. The wire + fetch are shipped and tested; the pip/egress runtime is
> provided by the Docker image (§13) but not yet exercised end-to-end.

## 8. Entity bridge, services & events

**Entity bridge (action-call forwarding).** Every proxy-entity method becomes a
standard `services.async_call(domain, service, target={"entity_id": [...]})`
round-trip over the shared `sandbox/call_service` channel. The sandbox's
`EntityBridge` pushes `register_entity` on an entity's first appearance (typed
`EntityDescription` grouping identity as `EntityInfo` and runtime state as
`InitialState`), then `state_changed` for updates. `register_entity` is an
**upsert** — post-setup name/icon/category/capability/device_info changes
re-send it and main refreshes the existing proxy in place (no duplicate).
Proxy `unique_id`s are prefixed with the source domain (`<domain>:<unique_id>`)
so two integrations in one group can't collide.

**Main gates registration on ownership, not just a resolvable id.**
`register_entity` is accepted only when `entry.sandbox == self.group` — the
sandbox may register entities solely for entries main routed to *this* group, so
a compromised sandbox cannot attach entities (or pre-create devices) against a
victim integration's config entry. A `device_info` whose identifiers/connections
collide with a device already owned by a config entry **outside** this group is
refused rather than merged, closing the device-registry hijack vector. Enforced
in `bridge.py` (`_handle_register_entity` / `_reject_foreign_device_merge`,
deriving trust from `entry.sandbox`).

On main, `SandboxBridge` instantiates a domain-typed proxy (all **31** domains
have one under `entity/`) and attaches it via the
`EntityComponent.async_register_remote_platform` core hook. Each outbound proxy
call sends one RPC; coalescing same-tick calls into a single multi-entity RPC
is a noted future optimisation. Exception translation rebuilds sandbox-side `vol.Invalid` /
`vol.MultipleInvalid` (with their `.path`) from a structured `error_data` frame
field, so callers on main see the local-entity error shape.

**Server-side queries (request/response).** The query-shaped entity APIs that
*ask* the entity a question now cross too. Ops with a `SupportsResponse` service
ride the existing `call_service` path with `return_response=True`
(`calendar.get_events`, `weather.get_forecasts`, `media_player.browse_media`);
the rest cross via a generic `sandbox/entity_query` RPC that names the entity
method + kwargs and returns the serialised result wrapped as `{"value": …}`
(`media_player.search_media`, `update.release_notes`, `vacuum.get_segments`, the
WS-only `calendar` event update/delete). Both decode the response with the
`as_dict`-aware JSON encoder on the sandbox side and rebuild the rich return
type (`BrowseMedia`, `CalendarEvent`, `SearchMedia`, `Segment`) on main with
explicit field mapping. Sandbox-raised errors propagate as channel error frames
and translate exactly like a service call. Still deferred: the
subscription/push primitive (`weather/subscribe_forecast`,
`calendar/event/subscribe`, the `todo` item-list push). Caveat: a sandboxed
`media_player`'s browse surfaces only its own sources — the `media_source` tree
runs on main, outside the boundary. See [`docs/query-shaped-rpcs.md`](docs/query-shaped-rpcs.md).

**Service & event mirroring.** After `async_setup_entry` succeeds, the entry's
domain joins a refcounted `ApprovedDomains` set that gates both mirrors.
`ServiceMirror` forwards `register_service` and installs a forwarder that
refuses to clobber an existing handler. The serialised service schema is a
best-effort optimisation (it lets main reject bad input without a round-trip);
any schema that doesn't survive serialisation degrades to no-schema on main and
the sandbox validates the call itself — a service is never dropped just because
its schema is exotic. `EventMirror` forwards only `<approved_domain>_*` events
via `sandbox/fire_event`; main re-fires them so automations react as if the
integration ran locally.

**Both mirror gates are re-enforced on main from main-side state — the
sandbox-side `ApprovedDomains` filter is advisory.** Main derives the group's
*owned domains* independently (`bridge.py` `_owned_domains`: the integration
domains of entries with `entry.sandbox == self.group`, plus its registered proxy
platform domains) and applies it to both inbound paths so they can't disagree:
`register_service` is rejected unless its `domain` is owned (no squatting
`persistent_notification.*` or any unclaimed `domain.service`); `fire_event` is
re-fired only when the event name falls in an owned `<domain>_` namespace **and**
is not a hard-denied core/control-plane event (`homeassistant_*`, `call_service`,
`state_changed`, …), so a forged `homeassistant_stop` or foreign `zha_event`
from a compromised sandbox is dropped, never re-fired. Enforced in `bridge.py`
(`_handle_register_service`, `_handle_fire_event` / `_is_event_allowed`).

**Context: the sandbox echoes ids, it never authors `Context`.** Only a
`context_id` (a string) crosses the wire — never `parent_id` or `user_id`. Main
**remembers every `Context` it hands down** to a sandbox (keyed by id, in a
15-minute-TTL cache on the bridge) at the call-down sites: the service
forwarder and the proxy-entity service call. When a sandbox event/state arrives
carrying an id main recognises, main restores the *original* `Context` (with
its real `parent_id` / `user_id`) verbatim, so a user-initiated action's
attribution survives the round-trip. An id main never issued (or one whose
entry has expired) gets a **brand-new** main-owned `Context(user_id=None)` — a
fresh id main generated with its own trusted clock, no fabricated parentage.
Main never adopts the sandbox-supplied id: `context_id`s are ULIDs carrying an
embedded millisecond timestamp, and a sandbox could craft one to back-/forward-
date an event (recorder / logbook order by it), so the sandbox string is used
only as the cache **key**, never as the resulting `Context`'s identity. A cache
miss is always safe — it degrades to a fresh context, never an error. Either
way the sandbox cannot invent a `parent_id` or impersonate a `user_id`. The
cache is size-bounded (`_CONTEXT_CACHE_MAX`) on **both** the remember and the
resolve paths (a single `_store_context` helper), so a sandbox flooding distinct
unknown `context_id`s can't grow it without bound. Enforced in `bridge.py`.

## 9. Store routing

`homeassistant.helpers.storage.Store` reads a `current_sandbox` **ContextVar**
(`homeassistant/helpers/sandbox_context.py`) at IO time. When set, the store's
`_async_load_data`, `_async_write_data`, and `async_remove` delegate to the
contextvar's `SandboxBridge` instead of local disk. Branching at
`_async_write_data` (not `async_save`) is deliberate: `async_save`,
`async_delay_save`, and the `FINAL_WRITE` flush all funnel through it, so one
branch covers every write path; the migration loop in `_async_load_data` runs
unchanged whether the envelope came from disk or the bridge.

The runtime sets `current_sandbox.set(ChannelSandboxBridge(channel))` right
after the channel opens and **before** the warm-load and any handler registers,
so every coroutine inherits it (asyncio copies the context at `create_task`).
This is a declared core hook, not a monkey-patch — and because it's read at
call time it reaches helpers like `restore_state` that captured the original
`Store` reference at import. On main, each bridge owns a `_SandboxStoreServer`
pinned to `<config>/.storage/sandbox/<group>/`, with strict key validation and
isolation-by-construction (one channel per group). Key validation includes a
length cap (well under `NAME_MAX`), and writes are quota-bounded — a per-key
value-size cap plus a per-group total-byte and key-count quota — so a compromised
sandbox cannot exhaust the host disk through the store channel; an over-quota
write is rejected with a clean error frame (the sandbox's `Store.async_save`
tolerates the failure and keeps its in-memory data). Enforced in `bridge.py`
(`_validate_key`, `_SandboxStoreServer._write_sync` / `_enforce_group_quota`).

## 10. Auth

The sandbox is **not an authenticated principal inside HA**: it never opens a
connection back to main and never acts on main's behalf, so it holds **no
credential and no user**. A sandbox-originated `Context` with no recognised id
is `user_id=None` (§8) — the honest shape, since no user authored it — so there
is nothing to fabricate. When a future websocket consumer needs the sandbox to
authenticate to main, the credential is designed then, with scopes (prior
thinking in the SUPERSEDED
[`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md)).

A richer attribution than `user_id=None` — a `Context` carrying which sandbox
**group** originated an action, for audit/logbook — is possible future work; it
needs a core `Context` field change (see [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md)).

Opt-in data sharing (state stream, entity/area registry) into the sandbox is a
future feature; the locked-down default (everything off) stands, with the
design in [`docs/design-share-states.md`](docs/design-share-states.md).

## 11. Translation forwarding

A sandboxed integration's frontend strings (entity names, entity-state
translations, config / options-flow labels, selectors, services, exceptions,
issues) live in its `translations/<lang>.json`, keyed by domain. Main serves
them to the frontend, but the integration runs in the sandbox — so a custom
integration's strings would otherwise silently resolve to `{}`
(`async_get_integrations` returns `IntegrationNotFound` as a dict value, which
the translation cache skips). Two seams close the gap:

- **Live pull (sandbox running).** A declared core hook
  (`async_register_sandbox_translation_provider` in `helpers/translation.py`)
  lets `_TranslationCache` overlay a provider's strings onto the per-language
  set *before* flattening, so they share the same English-fallback + cache
  machinery as disk strings. The component's `SandboxTranslationProvider`
  resolves a domain's group (a loaded entry's `ConfigEntry.sandbox`, or an
  in-progress flow's `SandboxFlowProxy.sandbox_group`), **carves out built-ins**
  (main reads its own identical disk copy — the RPC is custom-only), batches the
  rest into one `sandbox/get_translations` RPC per group/language, and
  **degrades to empty** on a dead/slow channel so the cache lock never wedges
  the frontend. The sandbox handler reuses core's string loader and pre-fills
  `title` from `integration.name` (main can't — it has no `Integration` for a
  custom). `async_invalidate_translations` evicts a domain's strings on entry
  reload, so a HACS update at a new `ref` re-pulls. **Main overlays only the
  domains it asked the group to resolve:** the provider keeps just the
  requested ∩ returned intersection, so a compromised sandbox can't return
  strings for a co-requested victim domain (`hue`, `http`) to poison its
  frontend strings. Enforced in `translation.py` (`async_get_translations`).
- **Picker (no sandbox running).** A separate, display-only catalog hook
  (`async_register_sandbox_catalog_provider` in `loader.py`, re-exported via
  `catalog.py`) lets HACS contribute `{domain, name, …, title_translations?}`
  entries that `async_get_integration_descriptions` merges into the
  add-integration dialog — so a sandbox-only custom is discoverable and named
  without spawning its sandbox. Kept separate from the sha-pinned source
  resolver; `title` degrades to `name`.

## 12. Core HA touch surface

The sandbox is deliberately small against core HA — five surfaces, each a
declared public hook rather than a reach into private internals:

- `config_entries.py` — the `router` attribute + `ConfigEntryRouter` Protocol (three call sites) and the first-class `ConfigEntry.sandbox` field.
- `helpers/entity_component.py` — `EntityComponent.async_register_remote_platform` (+ its inverse `async_unregister_remote_platform`), so a sandbox-built `EntityPlatform` attaches without re-discovering the local integration, and detaches cleanly on unload/respawn.
- `helpers/sandbox_context.py` (new) + `helpers/storage.py` — the `current_sandbox` ContextVar + `SandboxBridge` Protocol read by `Store`'s IO methods.
- `helpers/translation.py` — `async_register_sandbox_translation_provider` + the `_TranslationCache` overlay and `async_invalidate_translations` (§11).
- `loader.py` — `async_register_sandbox_catalog_provider` + the catalog merge in `async_get_integration_descriptions` (§11).

## 13. Testing & containerisation

Two pytest plugins under `hass_client/testing/` let HA Core's per-integration
suites run with the sandbox wired in; both share the manager-side
`SandboxBridge` path and differ only in how the channel pair is materialised
(in-process vs real subprocess). A protobuf round-trip drift guard keeps the
checked-in `_pb2` mirrors honest.

A multi-stage `python:3.14-slim` Docker image (`hass_client/Dockerfile`) runs
the runtime non-root with no persistent volumes — integration requirements are
pip-installed on demand, not baked. It talks to main over the unix-socket
transport (a same-host compose harness is templated; full remote operation
waits on the websocket transport). See
[`hass_client/docs/docker.md`](hass_client/docs/docker.md).

## 14. Out of scope / future work

- **WebSocket transport** — the seam is ready; lands with the share-states connection work.
- **State-sharing opt-in consumer** + main-side filtering ([`docs/design-share-states.md`](docs/design-share-states.md)); would let the lockdown helpers (§3) return to sandboxes.
- **Cross-sandbox in-process dependencies** — ESPHome serial / BLE proxy, and IR/RF command flows, where one integration depends on another's in-process surface across a sandbox boundary.
- **`Context` group attribute** (§10) — a core `Context` field naming which sandbox group originated an action, a richer audit answer than today's `user_id=None`. Context restoration from seen ids, dropping the unused token, and removing the per-group system user all **shipped** (`plans/plan-auth-context.md`); the wire still carries `context_id` only, so the sandbox can never fabricate attribution.
- **Query-shaped subscriptions** — the request/response RPCs shipped (§8: service-path + `entity_query`), so `calendar`/`weather`/`media_player`/`update`/`vacuum` queries answer with real data. What remains is the **subscription/push** primitive for the streaming `*/subscribe` commands (`weather/subscribe_forecast`, `calendar/event/subscribe`) and the `todo` item-list push that would un-block the `todo` platform, plus the `media_player.browse_media` media-source caveat (a sandboxed player's browse omits the main-side `media_source` tree). Full catalogue in [`docs/query-shaped-rpcs.md`](docs/query-shaped-rpcs.md).
- **pip/egress validation** for custom-integration dependencies in the container (§7).

## 15. Where to look in the code

The landing notes under [`status/`](status/) (`STATUS-phase-N.md` +
`STATUS-plan-*.md`) are the authoritative record of what each phase/plan
actually built, deferred, and flagged forward. For a quick map:

| Concern | HA Core side (`homeassistant/components/sandbox/`) | Sandbox side (`hass_client/hass_client/`) |
|---|---|---|
| Classifier | `classifier.py` | — |
| Lifecycle | `manager.py`, `__init__.py` | `sandbox/__init__.py`, `sandbox/__main__.py` |
| Channel / wire | `channel.py`, `codec_protobuf.py`, `messages.py` | `channel.py`, `codec_protobuf.py`, `messages.py` |
| Config flow | `router.py`, `proxy_flow.py`, `schema_bridge.py` | `flow_runner.py` |
| Entity bridge | `bridge.py`, `entity/` | `entry_runner.py`, `entity_bridge.py` |
| Service / event mirror | `bridge.py` | `service_mirror.py`, `event_mirror.py`, `approved_domains.py` |
| Context restoration | `bridge.py` (`_remember_context` / `_resolve_context`) | — |
| Store routing | `bridge.py` (`_SandboxStoreServer`), `helpers/sandbox_context.py`, `helpers/storage.py` | `sandbox_bridge.py` |
| Integration source | `sources.py` | `sources.py` |
| Translations | `translation.py`, `catalog.py`, `helpers/translation.py`, `loader.py` | `sandbox/__init__.py` (`_handle_get_translations`) |
| Shutdown | `__init__.py` (`_on_stop`), `manager.py` | `sandbox/__init__.py` (`_run_graceful_shutdown`) |
| Test infra | — | `testing/`, `run_compat.py` |

The wire-protocol constants live in two files that mirror each other verbatim:
`homeassistant/components/sandbox/protocol.py` and
`hass_client/hass_client/protocol.py` (along with the mirrored `channel.py` /
`codec_protobuf.py` / `messages.py`).

---

## Changelog

The architecture above is the result of the original phased build (Phases 0–20,
summarised in [`plan.md`](plan.md) and [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md))
followed by a closing batch that hardened the boundary and finished the
statelessness story. The closing batch, in landing order:

| Change | What it did |
|---|---|
| **current_sandbox ContextVar** | Replaced the module-level `Store` monkey-patch with a declared `current_sandbox` core-HA ContextVar; store IO routes to main at call time, reaching import-captured `Store` references the rebinding never could. (`plan-sandbox-context`, A1 + A2) |
| **Strip auth scopes** | Reverted the unused Phase-7 `RefreshToken.scopes` mechanism from core HA; the sandbox token is a plain system-user token. Re-introduced when a real websocket consumer lands. (`plan-strip-auth-scopes`) |
| **Protocol-fidelity batch** | CLI flag `--group`→`--name`; `vol.Invalid` reconstructed across the bridge with its `.path`; proxy `unique_id` prefixed with source domain; `register_entity` made an idempotent upsert; lossless `data_schema` (real selectors/sections) through the flow. (`plan-fidelity-batch`, #2/#7/#5/#6/#4) |
| **Lockdown → ALWAYS_MAIN** | Moved ~18 helper/aggregator integrations that read data they don't own onto main under the locked-down posture. (fidelity appendix / point 1) |
| **Protobuf wire + pluggable transports** | Rewrote the wire from JSON-lines to a three-layer Channel/Codec/Transport split: protobuf `Frame`s with typed per-message handlers (codec owns the registry), length-prefixed framing, a `Ready` frame replacing the text marker, and stdio + unix-socket transports. Context crosses as `context_id` only (no `parent_id`/`user_id` on the wire). WebSocket explicitly out of scope. (`plan-transport`, T1→T2→T3→T5) |
| **Stateless sandboxes** | `entry_setup` carries a typed `IntegrationSource`; custom (HACS) code is fetched at startup as a sha-pinned tarball via a HACS-agnostic resolver hook, with a process-lifetime cache. (`plan-ephemeral-sources`) |
| **Docker test image** | Multi-stage `python:3.14-slim` runtime image (non-root, no volumes, on-demand pip) + a unix-socket compose harness template. (`plan-docker`) |
| **Drop the `_v2` suffix** | Dropped the `_v2` suffix across directories, the integration domain, wire strings, storage namespace, protobuf, and the CLI module; removed the stale hassfest ignore. (`plan-rename-sandbox`) |
| **Drop token + system user, restore context** | Removed the unused `--token` / `SANDBOX_TOKEN` / `SandboxRuntime.token` end-to-end and deleted `auth.py` (per-group system user gone). Main now remembers every `Context` it hands down (15-min-TTL bridge cache, seeded at the service forwarder + proxy-entity call) and restores it verbatim on an echoed id; unknown/expired ids get a fresh main-owned `Context(user_id=None)` with main's own trusted id (never the untrusted sandbox ULID). (`plan-auth-context`, A/B/C) |
| **Trust-boundary hardening** | Moved the malicious-sandbox guarantees the docs assert onto main, re-derived from main-side state (`entry.sandbox == group` + owned proxy domains) rather than sandbox-supplied ids: `fire_event` owned-`<domain>_`-namespace + core deny-list gate, `register_service` owned-domain gate, `register_entity` `entry.sandbox` ownership + foreign-device-merge refusal, translation overlay narrowed to requested ∩ returned, store-server key-length + value/total/key-count quotas, context-cache eviction on the resolve path, and channel read-backpressure shedding (both mirrors). One adversarial forged-frame test per gate. (`plan-review-trust-boundary`, Phases 1–8) |
