# Sandbox — Architecture overview

> **Status:** Complete through Phase 20. The follow-up phases (12–20)
> closed every Phase 5–10 deferral; what remains of the original
> `share_states=True` deferral is now an explicit design
> ([`docs/design-share-states.md`](docs/design-share-states.md))
> rather than a wired-but-unused config flag. The chain: the concurrent
> channel dispatcher (Phase 12), all 32 domain proxies (Phase 13),
> `data_schema` / service-schema marshalling + `unique_id` propagation
> + the `async_unload_entry` core hook
> (Phase 14), the v1-baseline compat sweep (Phase 15), the
> 807-integration cross-sweep + categorised backlog (Phase 16), the
> `ConfigEntry.sandbox` field that lifted the test-level pass rate
> above the 99.5 % v1-removal threshold (Phase 17), the docs
> reconciliation pass (Phase 18), device-registry bridging (Phase 19),
> and the unwired `share_*` deletion + state-sharing design doc
> (Phase 20). v1 (`../sandbox/`) was removed 2026-05-28 — recover from
> git history if needed. See [`plan.md`](plan.md) for
> the phase-by-phase task list, [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md)
> for the narrative history of Phases 12+, and the
> [`status/`](status/) landing notes (`STATUS-phase-N.md` +
> `STATUS-plan-*.md`) for what each phase/plan shipped, what it
> deferred, and what it flagged forward.

## Goal

Run a Home Assistant integration's setup, config flow, entities,
services, and events fully inside an **isolated subprocess** ("sandbox"),
while the main HA instance keeps a **single, unified view** of devices,
entities, services, events, and translations that looks identical to
running everything locally.

A user adding a light integration through the frontend should end up
with a device + entities in the main instance's registries, area
targeting working (`light.turn_on` against an area resolves the
sandboxed lights like any other light), the integration's services +
events available on main — with the integration code only ever running
inside the sandbox.

## How the sandbox differs from the removed v1

| | v1 (removed) | current |
|---|---|---|
| Routing | `entry.options["sandbox"]` set by hand | Computed at runtime from manifest + platform inspection ([`classifier.py`](../homeassistant/components/sandbox/classifier.py)) |
| Transport | Live websocket connection back to main | Protobuf `Channel` over a pluggable transport (stdio by default, unix socket opt-in; websocket later) |
| Entity bridge | Bespoke `sandbox/update_state` + `sandbox/entity_command_result` (Option A) | Shared `sandbox/call_service` (Option B) — see [`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md) |
| Config flow | Forwarded through host integration | Runs inside the sandbox; main owns the canonical `ConfigEntry` store |
| Auth | System-user token, full HA scope | None — the sandbox is not an authenticated principal inside main; no token, no system user. A credential is redesigned (scopes included) when the sandbox→main connection lands |
| Data sharing | Sandbox sees all of main's state | Default locked-down; opt-in state/registry/area sharing per group is a future feature ([`docs/design-share-states.md`](docs/design-share-states.md)) |
| Store routing | None — sandbox writes to its own tempdir | The `current_sandbox` contextvar makes `Store` IO proxy to main; main writes to `<config>/.storage/sandbox/<group>/<key>` |
| Shutdown | Best-effort | Graceful `sandbox/shutdown` round-trip; sandbox unloads entries + dumps `RestoreEntity` state; main persists it for next boot |
| Custom integrations | Out of scope | First-class — they route to the `custom` group |

The design choices and the failure modes of v1 they fix are recorded in
[`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md) and
[`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md).

## High-level shape

```
┌──────────────────────────────── Home Assistant Core ─────────────────────────────────┐
│                                                                                       │
│  homeassistant/components/sandbox/                                                 │
│   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────────────┐    │
│   │ SandboxFlowRouter  │   │  SandboxManager    │   │   SandboxBridge (per group) │   │
│   │ • plugged into     │   │ • dict[group,      │   │ • proxy-entity registry    │    │
│   │   hass.config_     │   │   SandboxProcess]  │   │ • forwards entity service  │    │
│   │   entries.router   │   │ • lazy spawn per   │   │   calls via call_service   │    │
│   │ • routes flows +   │   │   group; restart   │   │ • re-fires sandbox events  │    │
│   │   entry setup      │   │   on crash         │   │ • per-group store server   │    │
│   └─────────┬──────────┘   └─────────┬──────────┘   └─────────────┬──────────────┘    │
│             │                        │                            │                   │
│             └────── classify() ──────┘                            │                   │
│                         │                                         │                   │
│                         ▼                                         │                   │
│             on first need: ensure_started(group)                  │                   │
└─────────────────────────┬─────────────────────────────────────────┼───────────────────┘
                          │                                         │
                          │  subprocess.Popen                       │  Channel
                          │  python -m hass_client.sandbox       │  (protobuf frames over
                          │  --name … --url …                       │   stdio / unix socket)
                          ▼                                         │
┌──────────────────────────── Sandbox subprocess ──────────────────────────────────────┐
│  sandbox/hass_client/hass_client/sandbox/__init__.py                                  │
│                                                                                       │
│  SandboxRuntime                                                                       │
│  • private HomeAssistant instance                                                     │
│  • current_sandbox.set(bridge) — routes Store IO to main via contextvar               │
│  • FlowRunner       — drives integration ConfigFlow on entry_init / step / abort     │
│  • EntryRunner      — runs async_setup_entry against the sandbox's hass              │
│  • EntityBridge     — pushes register_entity + state_changed to main                 │
│  • ServiceMirror    — pushes register_service for approved domains                   │
│  • EventMirror      — re-fires <approved_domain>_* events to main                    │
│  • ApprovedDomains  — refcounted set; gates ServiceMirror + EventMirror              │
│  • shutdown handler — unload entries, snapshot RestoreEntity state into reply        │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

## Routing rules

`classify(integration)` ([`classifier.py`](../homeassistant/components/sandbox/classifier.py))
is a pure function from a loaded `Integration` to a `SandboxAssignment`.
It runs from two places: `SandboxFlowRouter.async_create_flow` (new
flows) and `SandboxFlowRouter.async_setup_entry` (existing entries with
no `ConfigEntry.sandbox` value yet).

Rule order (first match wins):

1. `integration_type == "system"` → **main**. System integrations are
   part of the HA runtime; sandboxing them is meaningless.
2. `domain in ALWAYS_MAIN` → **main**. Hand-picked deny-list:
   `script`, `automation`, `scene`, `cloud`, `ai_task`, `image`. Each
   entry has an inline "why" in [`const.py`](../homeassistant/components/sandbox/const.py).
   `ai_task` and `image` were added by the Phase 1 spike because their
   service handlers do non-idempotent pre-dispatch work that neither
   bridge option intercepts cleanly — see the spike doc.
3. Any platform in `SANDBOX_INCOMPATIBLE_PLATFORMS` → **main**: `stt`,
   `tts`, `conversation`, `assist_satellite`, `wake_word`, `camera`.
   These exchange audio/byte streams the JSON channel can't ferry.
4. Custom (non-built-in) integration → `Sandbox("custom")`.
5. Otherwise → `Sandbox("built-in")`.

Three sandbox groups ship out of the box:

| Group | Hosts |
|---|---|
| `main` | nothing — anything in `ALWAYS_MAIN` or matching a deny-listed platform runs directly on main, no sandbox process |
| `built-in` | every other built-in integration |
| `custom` | every custom (HACS / user) integration |

State / entity-registry / area-registry sharing into the sandbox is a
future feature — Phase 7 added per-group `share_*` defaults but Phase
20 deleted them because nothing consumed them. See
[`docs/design-share-states.md`](docs/design-share-states.md) for the
design that will replace them.

The check uses `Integration.platforms_exists()` so the classifier never
imports the integration to make the call.

## Lifecycle

### Spawn

`SandboxManager.ensure_started(group)` is lazy: the subprocess starts
only when the first flow or entry routes to it. The subprocess command
is:

```
python -m hass_client.sandbox \
    --name <name> \
    --url stdio://
```

`--url` selects the control-channel transport: `stdio://` (the default —
frames ride the subprocess's stdin/stdout) or `unix://<path>` (the
manager opens a unix socket and the runtime dials back). `ws://` / `wss://`
are reserved for the deferred websocket transport and rejected for now.
The runtime opens the channel and sends a `Ready` frame
(`sandbox/ready`) as its first message; the manager treats its arrival
as "running" (there is no stdout text marker — stdout carries nothing but
channel frames). Frames are protobuf (a `Frame` envelope carrying one
typed message per `type`; `JsonCodec` is kept only for channel-core tests)
and length-prefixed (4-byte big-endian length + body) on the stream
transports. The three-layer split is `Channel` (dispatch core) → `Codec`
(`Frame` ↔ bytes; `ProtobufCodec` in production) → `Transport`
(`StreamTransport` length-prefixing over stdio / unix).

### Health & crash recovery

`SandboxProcess._supervise` watches the subprocess for unexpected exits.
Restart-on-crash is bounded: 3 attempts within a 60s sliding window,
with a small backoff sleep between attempts. Exceeding the budget
transitions the sandbox to `failed` and `ensure_started` raises
`SandboxFailedError` — the router surfaces this as
`SETUP_RETRY` on the affected entries.

A `sandbox/ping` handler is registered and exercised by the
subprocess test (`test_phase4_subprocess`); the periodic 30s ping loop
is wired through but currently disabled (process-exit detection covers
the hard-crash case).

### Graceful shutdown

On `EVENT_HOMEASSISTANT_STOP` the integration runs:

1. `manager.async_graceful_shutdown_all(timeout=manager.shutdown_grace)`
   fans out `sandbox/shutdown` to every running sandbox.
2. Each sandbox unloads its entries via `config_entries.async_unload`,
   snapshots `RestoreStateData.async_get_stored_states()` into a
   JSON-safe wrapped dict (round-tripped through orjson's HA-aware
   encoder), returns it in the reply, then schedules its own shutdown
   event via `call_soon` *after* the reply is queued so the subprocess
   exits 0 on its own.
3. The reply lands in `SandboxData`'s `on_shutdown_reply` callback,
   which writes `restore_state` to
   `<config>/.storage/sandbox/<group>/core.restore_state` via the
   bridge's store server.
4. `manager.async_stop_all()` falls through to SIGTERM, then SIGKILL,
   for any sandbox that didn't ack the graceful round-trip.

On the next boot the runtime warm-loads `core.restore_state` before any
handler registers, so the first `RestoreEntity.async_get_last_state()`
sees the previous run's state. It works against a vanilla `Store`: the
runtime sets `current_sandbox` before the warm-load, and `Store`'s IO
methods read the contextvar at call time, so the load routes to main even
though `restore_state.py` captured the original `Store` reference at
import. (Phase 8 needed an explicit sandbox-backed `Store` instance here
because its module-level rebinding couldn't reach that captured
reference; the contextvar made that workaround unnecessary.)

## Config-flow forwarding

The HA Core `ConfigEntries` object grows a single `router` attribute
([`config_entries.py`](../homeassistant/config_entries.py)) consulted
from three call sites:

- `ConfigEntriesFlowManager.async_create_flow` — when a new flow starts.
- `ConfigEntries.async_setup` — when an existing entry is being set up.
- `ConfigEntries.async_unload` — when an entry is being unloaded
  (Phase 14 hook on the same `router` attribute, same shape as the
  other two).

`SandboxFlowRouter.async_create_flow` runs the routing logic in order:
look up any existing entry for the handler key, fall back to
`classify(integration)`, then either return `None` (let HA handle it
locally) or hand back a `SandboxFlowProxy` `ConfigFlow`. The proxy
issues `sandbox/flow_init`, `sandbox/flow_step`, and
`sandbox/flow_abort` RPCs against the matching sandbox's runtime;
each RPC returns a marshalled `FlowResult` that the proxy re-issues as
`async_show_form` / `async_create_entry` / `async_abort` so the
framework treats the result as native.

Inside the sandbox, the integration's real `ConfigFlow` runs inside a
`_SandboxFlowManager` (a `ConfigEntriesFlowManager` subclass) that
short-circuits the CREATE_ENTRY path — main is the canonical owner of
the `ConfigEntry`, so the sandbox never tries to add an entry to its
own private store. When the sandbox returns a final `create_entry`
result, `SandboxFlowProxy._adapt_result` attaches `sandbox=<group>` to
the `ConfigFlowResult`; the framework's `ConfigEntry` constructor in
`ConfigEntriesFlowManager.async_finish_flow` reads
`result.get("sandbox")` and stores it on the new entry's first-class
`ConfigEntry.sandbox` field (Phase 17). On the next
`ConfigEntries.async_setup(entry_id)`, the router sees `entry.sandbox`,
ensures the sandbox is running, and round-trips an `entry_setup` RPC.

The flow proxy serialises `data_schema` via `voluptuous_serialize`
([`schema_bridge.py`](../homeassistant/components/sandbox/schema_bridge.py))
and rebuilds a `vol.Schema` on main so frontend forms render correctly
(Phase 14). The reconstruction rebuilds the real `Selector` /
`data_entry_flow.section` objects, so when the flow manager re-serialises
main's schema for the frontend it reproduces the sandbox's original list
verbatim — selectors keep their widget instead of degrading to plain text
boxes. The sandbox flow's `flow.context["unique_id"]`
rides in every marshalled `FlowResult` and the proxy applies it via
`async_set_unique_id`, so main's duplicate-detection guard fires for
collisions (Phase 14).

## Integration source — fetch before setup (stateless)

A sandbox holds no persistent state. Config is pushed on `entry_setup`,
storage/restore-state routes to main via the `current_sandbox` store
bridge — the last stateful bit was the **integration code itself**. Built-in
integrations ride the bundled `homeassistant` package, but custom (HACS)
integrations live under `<config>/custom_components` on the main install and
are absent from a fresh sandbox.

`entry_setup` therefore carries a typed `IntegrationSource` sub-message
(`EntrySetup.integration_source`):

- `{kind: "builtin"}` — the bundled package provides it; the sandbox does
  nothing.
- `{kind: "git", url, ref, tag, domain, subdir}` — main pushes where to fetch
  the code. `ref` is an **exact commit sha** (never a moving tag), so what the
  sandbox fetches can't be re-pointed between resolution and fetch.

**Main side** (`sources.py`): core stays HACS-agnostic via a registered
resolver hook. `async_register_sandbox_source_resolver(hass, resolver)` lets
HACS (or anything) map a custom domain → git source;
`async_resolve_integration_source` short-circuits built-ins to
`{kind: builtin}` (via `Integration.is_built_in`) and otherwise consults the
resolvers in order. With no resolver, a custom integration **raises** rather
than silently failing. The resolver is responsible for pinning the installed
version to a sha (core performs no network I/O); `tag` is logs-only.

**Sandbox side** (`hass_client/sources.py`):
`async_ensure_integration_source` runs **before** `async_setup`. A git source
downloads GitHub's codeload tarball for the exact sha (no `git` binary
dependency, matching HACS) and extracts the repo's `subdir` into
`<config>/custom_components/<domain>`, verifying the tree has a
`manifest.json`. A **process-lifetime cache** keyed by `(url, ref)` means
multiple entries from one repo download once; nothing survives a process
restart, so the sandbox stays wipe-and-restart safe. The download primitive is
injected so tests substitute a local fixture — no fetch ever hits the network.

## Entity bridge (Option B — action-call forwarding)

The Phase 1 spike compared two designs head-to-head and recorded
numbers in [`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md).
We picked **Option B**: every proxy entity method translates into a
standard `services.async_call("<domain>", "<service>",
target={"entity_id": [...]})` round-trip over the shared
`sandbox/call_service` channel.

### Sandbox side

`EntryRunner` rebuilds a `ConfigEntry` from the `sandbox/entry_setup`
payload, **fetches the integration's code** if needed (see below), drops the
entry into the sandbox's `ConfigEntries`, and runs the integration's
`async_setup_entry`. The integration adds entities the
normal way — `EntityBridge` listens for `EVENT_STATE_CHANGED` on the
sandbox's bus and, on each entity's first appearance, pushes
`sandbox/register_entity` to main with:

- `entry_id`, `domain`, `sandbox_entity_id`
- `unique_id` (prefixed on main with the source domain, `<domain>:<unique_id>`,
  so two integrations in one group can't collide), `name`, `icon`,
  `has_entity_name`
- `entity_category`, `device_class`, `supported_features`
- `capability_attributes` (`supported_color_modes`, color temp range, …)
- the initial `state` + `attributes`

Subsequent **state** updates push `sandbox/state_changed` (state +
attributes only). `register_entity` is an **upsert**: post-setup changes to
name / icon / category / capabilities / device_info arrive as
entity- and device-registry-updated events, which re-send
`register_entity` so main refreshes the existing proxy in place (no
duplicate entity).

### Main side

`SandboxBridge` receives `register_entity`, instantiates a
domain-specific proxy from
[`entity/`](../homeassistant/components/sandbox/entity/), and attaches
it to the matching `EntityComponent` via the new
`EntityComponent.async_register_remote_platform` core hook (Phase 5's
sole core change). The proxy holds a cached state + attributes dict
fed by `state_changed`; `state`, `available`, and per-domain typed
properties (`is_on`, `brightness`, `hs_color`, …) read from the cache.

Proxy method calls (e.g., `async_turn_on`) translate into one
`sandbox/call_service` RPC each. Coalescing same-tick calls for one service
into a single multi-entity RPC (so a 200-light area call pays one round-trip,
not 200) is a noted future optimisation — see
[`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md); the first iteration keeps it simple.

Exception translation rebuilds sandbox-side `vol.Invalid` /
`vol.MultipleInvalid` as the real exception (with its `.path`) from a
structured `error_data` field on the error frame, and maps
`ServiceNotFound` / `ServiceValidationError` → `HomeAssistantError`, so
callers on main see the local-entity error shape rather than a raw remote
error. (Frames without `error_data` fall back to the older class-name
mapping, where `vol.Invalid` → `TypeError`.)

### Domains shipped

All 32 supported domains have a typed proxy under
[`entity/`](../homeassistant/components/sandbox/entity/). Phase 5
shipped four (`light`, `switch`, `sensor`, `binary_sensor`) to prove
the path; Phase 13 added the remaining 28 mechanical follow-ups
(`alarm_control_panel`, `button`, `calendar`, `climate`, `cover`,
`date`, `datetime`, `device_tracker`, `event`, `fan`, `humidifier`,
`lawn_mower`, `lock`, `media_player`, `notify`, `number`, `remote`,
`scene`, `select`, `siren`, `text`, `time`, `todo`, `update`,
`vacuum`, `valve`, `water_heater`, `weather`). Each is a 20–80 LOC
`SandboxProxyEntity` subclass that wires the domain-typed properties
to the cache. Domains that index `supported_features` with `in`
re-wrap the wire int into the domain's `*EntityFeature` IntFlag in
`__init__`; four entities whose `state` is `@final` and reads a
name-mangled private field (`button`, `event`, `notify`, `scene`)
override `sandbox_apply_state` to set the mangled attribute directly.
Unknown-domain registrations still fall back to the generic
`SandboxProxyEntity` (state + attributes work; domain-typed properties
don't).

## Service & event mirroring

Once a sandboxed integration's `async_setup_entry` succeeds,
`EntryRunner` adds the entry's domain to a refcounted `ApprovedDomains`
set; `EntityBridge` also adds the domain of each registered entity (so
a sandbox that hosts a `light` integration approves the `light`
domain by virtue of registering light entities). `ServiceMirror` and
`EventMirror` consult this set before forwarding anything.

- **`ServiceMirror`** listens on the sandbox bus for
  `EVENT_SERVICE_REGISTERED` / `EVENT_SERVICE_REMOVED` and pushes
  `sandbox/register_service` / `unregister_service` (with
  `supports_response` and the serialised voluptuous schema via the
  Phase 14 `schema_bridge`). Main reconstructs the schema and passes
  it to `hass.services.async_register`, so bad service-call input is
  rejected on main without round-tripping. The sandbox still owns
  the real schema and runs full validation when the call lands on
  its `services.async_call`. Main installs a thin forwarder that
  ships each call back over the shared `sandbox/call_service`
  channel, reusing the Phase 5 exception translator. The forwarder
  **refuses to clobber an existing handler**, so the `light.turn_on`
  registered by the host `light` EntityComponent for our proxy
  entities keeps its dispatch role for entity services.

- **`EventMirror`** uses a `MATCH_ALL` listener with an internal-
  events deny-list and forwards only `<approved_domain>_*` events
  (e.g. `zha_event`, `mqtt_message_received`) via
  `sandbox/fire_event`. Main re-fires each on its own bus so
  `automation` listeners react as if the integration ran locally.
  The sandbox sends only a `context_id` string; main resolves it
  against the `Context` cache it seeds on every call-down (see
  *Context restoration* below), restoring the original
  `parent_id` / `user_id` for an id it issued or minting a fresh
  `user_id=None` `Context` (with main's own id) otherwise.

## Sandbox auth & opt-in data sharing

The sandbox is **not an authenticated principal inside main.** It never
opens a connection back to main and never acts on main's behalf, so it
needs no credential — and the `--token` the manager once minted was
**never read** by the runtime. `plan-auth-context.md` dropped it
end-to-end (no `--token` argv, no `SandboxRuntime.token`, no
`SANDBOX_TOKEN` env) and **removed the per-group system user**
(`auth.py` is gone). When the sandbox→main websocket actually lands
([`plans/plan-transport.md`](plans/plan-transport.md) T4), the
credential is a green-field redesign with a real consumer in hand —
scopes included; the prior thinking is preserved in
[`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md)
(marked SUPERSEDED).

### Context restoration

Only a `context_id` string ever crosses the wire — the protobuf
messages carry no `parent_id` / `user_id` field, so the sandbox can
never author a `Context`. Main **remembers every `Context` it hands
down** to a sandbox, keyed by id, at the two call-down sites: the
service forwarder (`_forward`) and the proxy entity's service call
(`async_call_service`). The store is a 15-minute-TTL cache on the
bridge — volume is tiny (a forwarded context is echoed back within the
same operation), so the TTL keeps it small and a miss is always safe.

On an inbound `state_changed` / `fire_event`, `_resolve_context`:

- **known id** (cached, not expired) → returns the original main-owned
  `Context` verbatim, so a user-initiated action's `parent_id` /
  `user_id` survive the main → sandbox → main round-trip;
- **unknown / expired id** → mints a **brand-new** `Context(user_id=None)`
  with main's **own** id, cached under the sandbox-supplied string.
  Main never adopts that string as the `Context`'s identity:
  `context_id`s are ULIDs with an embedded timestamp, and a sandbox
  could craft one to back-/forward-date an event (recorder / logbook
  order by it) — so the untrusted string is a cache **key** only.

A richer future answer (a `Context` group attribute naming the
originating sandbox) is noted in
[`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) but not built.

Opt-in data sharing (state stream, entity registry, area registry)
into the sandbox is a future feature. Phase 7 added unwired
`SharingConfig` / `SandboxGroupConfig` defaults; Phase 20 deleted them
because no consumer existed and replaced the surface with a design doc
([`docs/design-share-states.md`](docs/design-share-states.md)). The
locked-down posture stays — defaults are everything-off; the opt-in
subscription consumer lands behind whatever config surface the design
doc settles on.

## Store routing

`homeassistant.helpers.storage.Store` reads a `current_sandbox`
`ContextVar` (declared in
[`homeassistant/helpers/sandbox_context.py`](../homeassistant/helpers/sandbox_context.py))
at IO time. When it is set, `Store._async_load_data`,
`Store._async_write_data`, and `Store.async_remove` delegate to the
contextvar's `SandboxBridge` instead of touching local disk. Branching at
`_async_write_data` (not `async_save`) is deliberate: `async_save`,
`async_delay_save`, and the `EVENT_HOMEASSISTANT_FINAL_WRITE` flush all
funnel through `_async_handle_write_data` → `_async_write_data`, so one
branch there covers every write path. The migration loop in
`_async_load_data` runs unchanged regardless of whether the wrapped
envelope came from disk or the bridge.

The sandbox runtime supplies the bridge:
`ChannelSandboxBridge` ([`hass_client/sandbox_bridge.py`](hass_client/hass_client/sandbox_bridge.py))
implements the three `SandboxBridge` store methods over
`sandbox/store_load`, `sandbox/store_save`,
`sandbox/store_remove`. `SandboxRuntime.run` does
`current_sandbox.set(ChannelSandboxBridge(channel))` right after the
channel opens and **before** the warm-load and any per-runner handler
registers, so every coroutine the runtime spawns inherits it (asyncio
copies the context at `create_task` time). One sandbox process hosts one
sandbox group, so a single bridge per runtime is correct. This replaced
the Phase 8 module-level `Store` rebinding — no monkey-patch, and it
reaches helpers like `restore_state` that captured the original `Store`
reference at import.

On main, each `SandboxBridge` owns a `_SandboxStoreServer` pinned to
`<config>/.storage/sandbox/<group>/`. Writes use
`util.file.write_utf8_file_atomic` (the same primitive `Store` itself
uses). Scope isolation is by construction: each bridge owns one
channel for one group; forging a cross-group call would require
forging the channel. Key validation (`_require_key`) rejects `/`,
`\`, NUL, `.`, `..`, and any `..`-prefixed key before any path is
constructed.

Registries (entity/device/area/auth) that load during the sandbox's
startup *before* the channel is up keep their local tempdir backing.
Routing the HA-internals Stores too is a larger decision deferred to
post-launch.

## Test infrastructure

Two pytest plugins under
[`hass_client/hass_client/testing/`](hass_client/hass_client/testing/)
let HA Core's per-integration test suites run with sandbox wired
in. Both share the same manager-side `SandboxBridge` code path; the
only thing that differs is how the channel pair is materialised.

| Plugin | Wire | When to use |
|---|---|---|
| `hass_client.testing.pytest_plugin` | in-memory channel pair, `SandboxRuntime` as an asyncio task | fast feedback, freezer-safe |
| `hass_client.testing.conftest_sandbox` | real stdio protobuf channel (`python -m hass_client.sandbox`) | pins the subprocess boundary, freezer tests auto-skip |

The compat lane runner
[`run_compat.py`](run_compat.py) drives either plugin against a list of
integration test directories, parses pytest's summary line, and writes a
machine CSV plus a `COMPAT_LATEST.md` per-run report (both git-ignored). The
curated baseline lives in [`COMPAT.md`](COMPAT.md) and the curated residual
backlog in [`BACKLOG.md`](BACKLOG.md). Per-failure output lands in
`${SANDBOX_ERRORS_DIR:-/tmp/sandbox_errors}`.

The one-shot full cross-sweep tooling that produced the original backlog
(`run_compat_full.py` + `categorize_failures.py` + `generate_backlog.py`) was
removed once the measurement was done; recover it from git history if a fresh
tree-wide sweep is ever needed.

**Baseline numbers (Phase 17):** 35/37 integrations pass on the
v1-baseline 37-integration set (99.97 % test-level); 711/807
integrations pass on the broader sweep (99.67 % test-level — above the
99.5 % v1-removal threshold the plan asked for).

## Where the design is still open

These are the items the per-phase STATUS files flagged forward as
explicit non-goals for the sandbox's first pass. They're tracked separately so
the sandbox itself stays reviewable. The closed-since-Phase-11 items are listed
in [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) with the causal chain to
the phase that resolved each one.

- **State-sharing subscription consumer + main-side filtering.**
  Phase 20 deleted the unwired `SharingConfig` / `SandboxGroupConfig`
  surface and replaced it with a design
  ([`docs/design-share-states.md`](docs/design-share-states.md))
  covering the entity_id alignment constraint, the
  `share/subscribe_*` protocol, the main-side filter, and the
  remaining open questions. The actual consumer + main-side handlers
  are owed in a future phase against that design.
- **Non-idempotent service handlers** (`ai_task` and friends).
  Punted to `ALWAYS_MAIN` for the sandbox; a future spec on service-handler-level
  interception or sandbox-aware integration hooks is the long-term
  fix. The Phase 1 spike doc has the full write-up.
- **v1 removal. DONE (2026-05-28).** The numeric gate Phase 11 set was
  satisfied by Phases 15–17 (99.67 % full-sweep; 99.97 % v1-baseline).
  v1 (`sandbox/` + `homeassistant/components/sandbox/` +
  `tests/components/sandbox/`) was removed ahead of the "shipped a stable
  release" condition, relying on git history for rollback.
- **`calendar` / `todo` / `weather` query-shaped RPCs.** `async_get_events`
  (calendar), `todo_items` (todo), and `weather.async_forecast_*`
  return server-side query results the action-call channel can't
  express. The Phase 13 proxies return empty lists for these; a
  separate query-shaped RPC is owed if the compat sweep ever surfaces
  an integration that depends on these surfaces (it hasn't yet — see
  [`BACKLOG.md`](BACKLOG.md)).
- **Diagnostic snapshot drift.** ~30 integrations have
  `__snapshots__/` files that include `entry.as_dict()` and now show
  `+ 'sandbox': 'built-in'`. The fix lives in those integrations'
  trees (`pytest --snapshot-update` per integration). Optional Phase
  17b: a clock-pinning fixture autouse on the compat plugin (~30
  LOC, sketched in `BACKLOG.md`) would also mask the `created_at`
  drift driving ~70 of the 112 residual failures.
- **Cross-sandbox in-process dependencies (ESPHome serial / BLE
  proxy).** Some integration pairs are coupled in-process: an ESPHome
  device exposing a serial-over-TCP proxy that a downstream
  integration (ZHA, zwave_js, deCONZ, …) connects to, or ESPHome BLE
  proxy advertisements being forwarded to the `bluetooth`
  integration. Today these only work if both integrations end up in
  the same sandbox group — the setup-time coordination (proxy
  enumeration, port handoff, BLE advert forwarding) happens via
  Python calls/events the bridge doesn't cross. The current
  classifier puts all built-in integrations into one `built-in`
  sandbox, so the pure-built-in case is fine; the trip wire is a
  built-in integration paired with a custom variant of the consumer,
  which would split across the `built-in` / `custom` groups. Fix
  shape: either a "co-locate with X" classifier hint for known
  coupled pairs, or extend the Phase 6 event mirror beyond
  `<owned_domain>_*` to cover the coordination hooks. IR / RF
  (Broadlink-style command remotes) are simpler — one-way command
  flows with no setup-time enumeration or bidirectional stream — but
  still need dedicated cross-sandbox support to route the consumer's
  send-call to the producer. Worth a small spec before any real split
  trips it.

## Where to look in the code

The landing notes under [`status/`](status/) (`STATUS-phase-N.md` +
`STATUS-plan-*.md`) are the authoritative record of what each phase/plan
actually built, what it deferred, and what it flagged forward. For a quick map:

| Concern | HA Core side | Sandbox side |
|---|---|---|
| Classifier | [`classifier.py`](../homeassistant/components/sandbox/classifier.py) | — |
| Lifecycle | [`manager.py`](../homeassistant/components/sandbox/manager.py) | [`sandbox.py`](hass_client/hass_client/sandbox/__init__.py), [`sandbox/__main__.py`](hass_client/hass_client/sandbox/__main__.py) |
| Channel | [`channel.py`](../homeassistant/components/sandbox/channel.py) | [`channel.py`](hass_client/hass_client/channel.py) |
| Config flow | [`router.py`](../homeassistant/components/sandbox/router.py), [`proxy_flow.py`](../homeassistant/components/sandbox/proxy_flow.py) | [`flow_runner.py`](hass_client/hass_client/flow_runner.py) |
| Entity bridge | [`bridge.py`](../homeassistant/components/sandbox/bridge.py), [`entity/`](../homeassistant/components/sandbox/entity/) | [`entry_runner.py`](hass_client/hass_client/entry_runner.py), [`entity_bridge.py`](hass_client/hass_client/entity_bridge.py) |
| Service/event mirror | [`bridge.py`](../homeassistant/components/sandbox/bridge.py) | [`service_mirror.py`](hass_client/hass_client/service_mirror.py), [`event_mirror.py`](hass_client/hass_client/event_mirror.py), [`approved_domains.py`](hass_client/hass_client/approved_domains.py) |
| Context restoration | [`bridge.py`](../homeassistant/components/sandbox/bridge.py) (`_remember_context` / `_resolve_context`, TTL cache) | — |
| Store routing | [`bridge.py`](../homeassistant/components/sandbox/bridge.py) (`_SandboxStoreServer`), `homeassistant/helpers/sandbox_context.py`, `homeassistant/helpers/storage.py` | [`sandbox_bridge.py`](hass_client/hass_client/sandbox_bridge.py) |
| Shutdown | [`__init__.py`](../homeassistant/components/sandbox/__init__.py) (`_on_stop`), `manager.py` | [`sandbox.py`](hass_client/hass_client/sandbox/__init__.py) (`_run_graceful_shutdown`) |
| Test infra | — | [`testing/`](hass_client/hass_client/testing/), [`run_compat.py`](run_compat.py) |

The wire protocol constants live in two files that mirror each other
verbatim:
[`homeassistant/components/sandbox/protocol.py`](../homeassistant/components/sandbox/protocol.py)
and [`sandbox/hass_client/hass_client/protocol.py`](hass_client/hass_client/protocol.py).
