# Sandbox v2 — Architecture overview

> **Status:** Complete through Phase 17. The follow-up phases (12–17)
> closed every Phase 5–10 deferral except the `share_states=True`
> subscription consumer: the concurrent channel dispatcher (Phase 12),
> all 32 domain proxies (Phase 13), `data_schema` / service-schema
> marshalling + `unique_id` propagation + the 200-light perf benchmark
> + the `async_unload_entry` core hook (Phase 14), the v1-baseline
> compat sweep (Phase 15), the 807-integration cross-sweep + categorised
> backlog (Phase 16), and the `ConfigEntry.sandbox` field that lifted
> the test-level pass rate above the 99.5 % v1-removal threshold
> (Phase 17). v1 (`../sandbox/`) is kept around for reference until v2
> has shipped at least one stable release. See [`plan.md`](plan.md) for
> the phase-by-phase task list, [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md)
> for the narrative history of Phases 12–17, and the per-phase
> `STATUS-phase-N.md` files for what each phase shipped, what it
> deferred, and what it flagged forward.

## Goal

Run a Home Assistant integration's setup, config flow, entities,
services, and events fully inside an **isolated subprocess** ("sandbox"),
while the main HA instance keeps a **single, unified view** of devices,
entities, services, and events that looks identical to running
everything locally.

A user adding a light integration through the frontend should end up
with a device + entities in the main instance's registries, area
targeting working (`light.turn_on` against an area resolves the
sandboxed lights like any other light), the integration's services +
events available on main — with the integration code only ever running
inside the sandbox.

## How v2 differs from v1

| | v1 (`sandbox/`) | v2 (`sandbox_v2/`) |
|---|---|---|
| Routing | `entry.options["sandbox"]` set by hand | Computed at runtime from manifest + platform inspection ([`classifier.py`](../homeassistant/components/sandbox_v2/classifier.py)) |
| Transport | Live websocket connection back to main | JSON-line `Channel` over the subprocess's stdin/stdout |
| Entity bridge | Bespoke `sandbox/update_state` + `sandbox/entity_command_result` (Option A) | Shared `sandbox_v2/call_service` (Option B) — see [`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md) |
| Config flow | Forwarded through host integration | Runs inside the sandbox; main owns the canonical `ConfigEntry` store |
| Auth | System-user token, full HA scope | Scoped `RefreshToken` (`{"sandbox_v2/", "auth/current_user"}`); dispatcher rejects out-of-scope calls |
| Data sharing | Sandbox sees all of main's state | Default locked-down; opt-in `share_states` / `share_entity_registry` / `share_areas` per group |
| Store routing | None — sandbox writes to its own tempdir | `RemoteStore` proxies every `Store(...)` to main; main writes to `<config>/.storage/sandbox_v2/<group>/<key>` |
| Shutdown | Best-effort | Graceful `sandbox_v2/shutdown` round-trip; sandbox unloads entries + dumps `RestoreEntity` state; main persists it for next boot |
| Custom integrations | Out of scope | First-class — they route to the `custom` group |

The design choices and the failure modes of v1 they fix are recorded in
[`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md) and
[`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md).

## High-level shape

```
┌──────────────────────────────── Home Assistant Core ─────────────────────────────────┐
│                                                                                       │
│  homeassistant/components/sandbox_v2/                                                 │
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
                          │  python -m hass_client.sandbox_v2       │  (JSON lines over
                          │  --group … --url … --token …            │   stdin/stdout)
                          ▼                                         │
┌──────────────────────────── Sandbox subprocess ──────────────────────────────────────┐
│  sandbox_v2/hass_client/hass_client/sandbox.py                                       │
│                                                                                       │
│  SandboxRuntime                                                                       │
│  • private HomeAssistant instance                                                     │
│  • install_remote_store(channel) — rebinds storage.Store to RemoteStore               │
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

`classify(integration)` ([`classifier.py`](../homeassistant/components/sandbox_v2/classifier.py))
is a pure function from a loaded `Integration` to a `SandboxAssignment`.
It runs from two places: `SandboxFlowRouter.async_create_flow` (new
flows) and `SandboxFlowRouter.async_setup_entry` (existing entries with
no `ConfigEntry.sandbox` value yet).

Rule order (first match wins):

1. `integration_type == "system"` → **main**. System integrations are
   part of the HA runtime; sandboxing them is meaningless.
2. `domain in ALWAYS_MAIN` → **main**. Hand-picked deny-list:
   `script`, `automation`, `scene`, `cloud`, `ai_task`, `image`. Each
   entry has an inline "why" in [`const.py`](../homeassistant/components/sandbox_v2/const.py).
   `ai_task` and `image` were added by the Phase 1 spike because their
   service handlers do non-idempotent pre-dispatch work that neither
   bridge option intercepts cleanly — see the spike doc.
3. Any platform in `SANDBOX_INCOMPATIBLE_PLATFORMS` → **main**: `stt`,
   `tts`, `conversation`, `assist_satellite`, `wake_word`, `camera`.
   These exchange audio/byte streams the JSON channel can't ferry.
4. Custom (non-built-in) integration → `Sandbox("custom")`.
5. Otherwise → `Sandbox("built-in")`.

Three sandbox groups ship out of the box:

| Group | Hosts | Default sharing |
|---|---|---|
| `main` | nothing — anything in `ALWAYS_MAIN` or matching a deny-listed platform runs directly on main, no sandbox process | n/a |
| `built-in` | every other built-in integration | `share_states`, `share_entity_registry`, `share_areas` all `True` |
| `custom` | every custom (HACS / user) integration | all sharing `False` (locked down) |

The check uses `Integration.platforms_exists()` so the classifier never
imports the integration to make the call.

## Lifecycle

### Spawn

`SandboxManager.ensure_started(group)` is lazy: the subprocess starts
only when the first flow or entry routes to it. The subprocess command
is:

```
python -m hass_client.sandbox_v2 \
    --group <group> \
    --url ws://localhost:8123/api/websocket \
    --token <scoped sandbox access token> \
    [--share-states] [--share-entity-registry] [--share-areas]
```

The runtime prints `sandbox_v2:ready` on stdout once its
`HomeAssistant` instance is up; the manager parses that marker, then
opens a `Channel` over the subprocess's remaining stdin/stdout traffic.
Everything after the marker is JSON-line framed (one message per line,
length-delimited at the newline).

### Health & crash recovery

`SandboxProcess._supervise` watches the subprocess for unexpected exits.
Restart-on-crash is bounded: 3 attempts within a 60s sliding window,
with a small backoff sleep between attempts. Exceeding the budget
transitions the sandbox to `failed` and `ensure_started` raises
`SandboxFailedError` — the router surfaces this as
`SETUP_RETRY` on the affected entries.

A `sandbox_v2/ping` handler is registered and exercised by the
subprocess test (`test_phase4_subprocess`); the periodic 30s ping loop
is wired through but currently disabled (process-exit detection covers
the hard-crash case).

### Graceful shutdown

On `EVENT_HOMEASSISTANT_STOP` the integration runs:

1. `manager.async_graceful_shutdown_all(timeout=manager.shutdown_grace)`
   fans out `sandbox_v2/shutdown` to every running sandbox.
2. Each sandbox unloads its entries via `config_entries.async_unload`,
   snapshots `RestoreStateData.async_get_stored_states()` into a
   JSON-safe wrapped dict (round-tripped through orjson's HA-aware
   encoder), returns it in the reply, then schedules its own shutdown
   event via `call_soon` *after* the reply is queued so the subprocess
   exits 0 on its own.
3. The reply lands in `SandboxV2Data`'s `on_shutdown_reply` callback,
   which writes `restore_state` to
   `<config>/.storage/sandbox_v2/<group>/core.restore_state` via the
   bridge's store server.
4. `manager.async_stop_all()` falls through to SIGTERM, then SIGKILL,
   for any sandbox that didn't ack the graceful round-trip.

On the next boot the runtime warm-loads `core.restore_state` via an
explicit `RemoteStore(hass, …, encoder=JSONEncoder)` before any handler
registers, so the first `RestoreEntity.async_get_last_state()` sees the
previous run's state. The warm-load can't go through the storage-module
rebinding because `restore_state.py` captures `Store` at import time —
the explicit `RemoteStore` instance is the workaround.

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
issues `sandbox_v2/flow_init`, `sandbox_v2/flow_step`, and
`sandbox_v2/flow_abort` RPCs against the matching sandbox's runtime;
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
([`schema_bridge.py`](../homeassistant/components/sandbox_v2/schema_bridge.py))
and rebuilds a permissive `vol.Schema` on main so frontend forms render
field hints (Phase 14). The sandbox flow's `flow.context["unique_id"]`
rides in every marshalled `FlowResult` and the proxy applies it via
`async_set_unique_id`, so main's duplicate-detection guard fires for
collisions (Phase 14).

## Entity bridge (Option B — action-call forwarding)

The Phase 1 spike compared two designs head-to-head and recorded
numbers in [`docs/entity-bridge-decision.md`](docs/entity-bridge-decision.md).
We picked **Option B**: every proxy entity method translates into a
standard `services.async_call("<domain>", "<service>",
target={"entity_id": [...]})` round-trip over the shared
`sandbox_v2/call_service` channel.

### Sandbox side

`EntryRunner` rebuilds a `ConfigEntry` from the `sandbox_v2/entry_setup`
payload, drops it into the sandbox's `ConfigEntries`, and runs the
integration's `async_setup_entry`. The integration adds entities the
normal way — `EntityBridge` listens for `EVENT_STATE_CHANGED` on the
sandbox's bus and, on each entity's first appearance, pushes
`sandbox_v2/register_entity` to main with:

- `entry_id`, `domain`, `sandbox_entity_id`
- `unique_id`, `name`, `icon`, `has_entity_name`
- `entity_category`, `device_class`, `supported_features`
- `capability_attributes` (`supported_color_modes`, color temp range, …)
- the initial `state` + `attributes`

Subsequent updates push `sandbox_v2/state_changed` (state + attributes
only — no re-registration).

### Main side

`SandboxBridge` receives `register_entity`, instantiates a
domain-specific proxy from
[`entity/`](../homeassistant/components/sandbox_v2/entity/), and attaches
it to the matching `EntityComponent` via the new
`EntityComponent.async_register_remote_platform` core hook (Phase 5's
sole core change). The proxy holds a cached state + attributes dict
fed by `state_changed`; `state`, `available`, and per-domain typed
properties (`is_on`, `brightness`, `hs_color`, …) read from the cache.

Proxy method calls (e.g., `async_turn_on`) translate into
`sandbox_v2/call_service` RPCs via a per-loop-tick batcher
(`_CallServiceBatcher`) that coalesces matching
`(domain, service, service_data)` calls into one multi-entity RPC — so
a 200-light area call pays one RPC, not 200.

Exception translation maps sandbox-side `vol.Invalid` →
`TypeError` and `ServiceNotFound` / `ServiceValidationError` →
`HomeAssistantError`, so callers on main see the local-entity error
shape rather than a raw remote error.

### Domains shipped

All 32 supported domains have a typed proxy under
[`entity/`](../homeassistant/components/sandbox_v2/entity/). Phase 5
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

The Phase 14 perf benchmark
([`test_perf.py`](../tests/components/sandbox_v2/test_perf.py))
registers 200 proxy lights, area-targets `light.turn_on`, and asserts
the batcher coalesces the 200 entity invocations into ≤2 RPCs in under
500 ms. A regression that broke same-tick coalescing would fail
loudly.

## Service & event mirroring

Once a sandboxed integration's `async_setup_entry` succeeds,
`EntryRunner` adds the entry's domain to a refcounted `ApprovedDomains`
set; `EntityBridge` also adds the domain of each registered entity (so
a sandbox that hosts a `light` integration approves the `light`
domain by virtue of registering light entities). `ServiceMirror` and
`EventMirror` consult this set before forwarding anything.

- **`ServiceMirror`** listens on the sandbox bus for
  `EVENT_SERVICE_REGISTERED` / `EVENT_SERVICE_REMOVED` and pushes
  `sandbox_v2/register_service` / `unregister_service` (with
  `supports_response` and the serialised voluptuous schema via the
  Phase 14 `schema_bridge`). Main reconstructs the schema and passes
  it to `hass.services.async_register`, so bad service-call input is
  rejected on main without round-tripping. The sandbox still owns
  the real schema and runs full validation when the call lands on
  its `services.async_call`. Main installs a thin forwarder that
  ships each call back over the shared `sandbox_v2/call_service`
  channel, reusing the Phase 5 exception translator. The forwarder
  **refuses to clobber an existing handler**, so the `light.turn_on`
  registered by the host `light` EntityComponent for our proxy
  entities keeps its dispatch role for entity services.

- **`EventMirror`** uses a `MATCH_ALL` listener with an internal-
  events deny-list and forwards only `<approved_domain>_*` events
  (e.g. `zha_event`, `mqtt_message_received`) via
  `sandbox_v2/fire_event`. Main re-fires each on its own bus so
  `automation` listeners react as if the integration ran locally.
  The sandbox's `context_id` is on the wire but main does **not**
  honour it on the re-fire (a fresh local `Context` is used) —
  carrying a richer `Context` shape across the bridge is post-v2
  work.

## Scoped auth & opt-in data sharing

`RefreshToken` gains an optional `scopes: frozenset[str] | None` field
([`homeassistant/auth/models.py`](../homeassistant/auth/models.py)). The
websocket dispatcher
([`websocket_api/connection.py`](../homeassistant/components/websocket_api/connection.py))
checks each incoming command via a module-level `_scope_allows` helper
that matches prefix grants (`sandbox_v2/`) and exact-match entries
(`auth/current_user`); unscoped tokens (`scopes is None`) are
unaffected.

The sandbox issuance helper
([`auth.py`](../homeassistant/components/sandbox_v2/auth.py)) creates a
dedicated system user per group and a scoped refresh token with
`scopes = {"sandbox_v2/", "auth/current_user"}`. Result: a
sandboxed integration cannot call `light.turn_on`, `auth/sign_path`,
or any other non-`sandbox_v2/` command — the dispatcher rejects with
`ERR_UNAUTHORIZED` before the handler runs.

Opt-in data sharing lands as `SandboxGroupConfig` with three flags
(`share_states`, `share_entity_registry`, `share_areas`). Defaults:
`built-in` and `main` everything on; `custom` everything off. The
runtime accepts matching `--share-*` CLI flags into a `SharingConfig`
dataclass. The sandbox→main subscription consumer that hangs off these
flags is **not yet implemented** — the locked-down posture is enforced
trivially today (no subscription code exists). Filtering on main's
side is owed in the same PR.

The full decision rationale lives in
[`docs/auth-scoping-decision.md`](docs/auth-scoping-decision.md).

## Store routing

`RemoteStore` ([`hass_client/remote_store.py`](hass_client/hass_client/remote_store.py))
subclasses `homeassistant.helpers.storage.Store` and overrides the
three IO primitives — `_async_load_data`, `_async_write_data`,
`async_remove` — to talk to main via `sandbox_v2/store_load`,
`sandbox_v2/store_save`, `sandbox_v2/store_remove`. `delay_save`, the
`EVENT_HOMEASSISTANT_FINAL_WRITE` hook, and the migration loop run
unchanged from the base class.

`install_remote_store(channel)` runs right after the sandbox channel
opens and before any per-runner handler registers. It rebinds
`homeassistant.helpers.storage.Store` to `RemoteStore` for the lifetime
of the sandbox process, so every `Store(...)` instantiated during
`async_setup_entry` is a `RemoteStore`. The patch is process-wide
because one sandbox process hosts one sandbox group.

On main, each `SandboxBridge` owns a `_SandboxStoreServer` pinned to
`<config>/.storage/sandbox_v2/<group>/`. Writes use
`util.file.write_utf8_file_atomic` (the same primitive `Store` itself
uses). Scope isolation is by construction: each bridge owns one
channel for one group; forging a cross-group call would require
forging the channel. Key validation (`_require_key`) rejects `/`,
`\`, NUL, `.`, `..`, and any `..`-prefixed key before any path is
constructed.

Registries (entity/device/area/auth) that load during the sandbox's
startup *before* the channel is up keep their local tempdir backing.
Routing the HA-internals Stores too is a larger decision deferred to
post-v2.

## Test infrastructure

Two pytest plugins under
[`hass_client/hass_client/testing/`](hass_client/hass_client/testing/)
let HA Core's per-integration test suites run with sandbox_v2 wired
in. Both share the same manager-side `SandboxBridge` code path; the
only thing that differs is how the channel pair is materialised.

| Plugin | Wire | When to use |
|---|---|---|
| `hass_client.testing.pytest_plugin` | in-memory channel pair, `SandboxRuntime` as an asyncio task | fast feedback, freezer-safe |
| `hass_client.testing.conftest_sandbox` | real stdio JSON-line (`python -m hass_client.sandbox_v2`) | pins the subprocess boundary, freezer tests auto-skip |

The compat lane runner
[`run_compat.py`](run_compat.py) drives either plugin against a list of
integration test directories, parses pytest's summary line, and writes
[`COMPAT.csv`](COMPAT.csv) + [`COMPAT_LATEST.md`](COMPAT_LATEST.md)
(the curated baseline lives in [`COMPAT.md`](COMPAT.md)). Per-failure
output lands in `${SANDBOX_V2_ERRORS_DIR:-/tmp/sandbox_v2_errors}`.

[`run_compat_full.py`](run_compat_full.py) is the wider cross-sweep
runner Phase 16 landed: asyncio + JUnit XML + outer concurrency,
exercises every classifier-routable integration in the tree and writes
[`COMPAT_FULL.md`](COMPAT_FULL.md) + [`COMPAT_FULL.csv`](COMPAT_FULL.csv).
[`categorize_failures.py`](categorize_failures.py) buckets the
JUnit failures into [`BACKLOG.md`](BACKLOG.md) +
[`BACKLOG_FAILURES.json`](BACKLOG_FAILURES.json).

**Baseline numbers (Phase 17):** 35/37 integrations pass on the
v1-baseline 37-integration set (99.97 % test-level); 711/807
integrations pass on the broader sweep (99.67 % test-level — above the
99.5 % v1-removal threshold the plan asked for).

## Where the design is still open

These are the items the per-phase STATUS files flagged forward as
explicit non-goals for v2's first pass. They're tracked separately so
v2 itself stays reviewable. The closed-since-Phase-11 items are listed
in [`docs/FOLLOWUPS.md`](docs/FOLLOWUPS.md) with the causal chain to
the phase that resolved each one.

- **`share_states=True` subscription consumer + main-side filtering.**
  The config flag is wired; the consumer that opens a subscription
  back to main and the filtering on main's emit path are owed in the
  same PR.
- **Non-idempotent service handlers** (`ai_task` and friends).
  Punted to `ALWAYS_MAIN` for v2; a v3 spec on service-handler-level
  interception or sandbox-aware integration hooks is the long-term
  fix. The Phase 1 spike doc has the full write-up.
- **v1 removal.** The numeric gate Phase 11 set (match v1's compat
  numbers) is **now satisfied** by Phases 15–17 (99.67 % full-sweep
  pass rate clears the 99.5 % threshold; 99.97 % on the v1-baseline
  37-integration set). The remaining condition — v2 has shipped at
  least one stable release — is a release-process step. Keep
  `sandbox/` and `homeassistant/components/sandbox/` around until
  that ships, then queue v1 removal for the release after.
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

## Where to look in the code

The per-phase `STATUS-phase-N.md` files in this directory are the
authoritative record of what each phase actually built, what it
deferred, and what it flagged for the next phase. For a quick map:

| Concern | HA Core side | Sandbox side |
|---|---|---|
| Classifier | [`classifier.py`](../homeassistant/components/sandbox_v2/classifier.py) | — |
| Lifecycle | [`manager.py`](../homeassistant/components/sandbox_v2/manager.py) | [`sandbox.py`](hass_client/hass_client/sandbox.py), [`sandbox_v2/__main__.py`](hass_client/hass_client/sandbox_v2/__main__.py) |
| Channel | [`channel.py`](../homeassistant/components/sandbox_v2/channel.py) | [`channel.py`](hass_client/hass_client/channel.py) |
| Config flow | [`router.py`](../homeassistant/components/sandbox_v2/router.py), [`proxy_flow.py`](../homeassistant/components/sandbox_v2/proxy_flow.py) | [`flow_runner.py`](hass_client/hass_client/flow_runner.py) |
| Entity bridge | [`bridge.py`](../homeassistant/components/sandbox_v2/bridge.py), [`entity/`](../homeassistant/components/sandbox_v2/entity/) | [`entry_runner.py`](hass_client/hass_client/entry_runner.py), [`entity_bridge.py`](hass_client/hass_client/entity_bridge.py) |
| Service/event mirror | [`bridge.py`](../homeassistant/components/sandbox_v2/bridge.py) | [`service_mirror.py`](hass_client/hass_client/service_mirror.py), [`event_mirror.py`](hass_client/hass_client/event_mirror.py), [`approved_domains.py`](hass_client/hass_client/approved_domains.py) |
| Auth scopes | [`auth.py`](../homeassistant/components/sandbox_v2/auth.py), `homeassistant/auth/models.py`, `homeassistant/components/websocket_api/connection.py` | — |
| Store routing | [`bridge.py`](../homeassistant/components/sandbox_v2/bridge.py) (`_SandboxStoreServer`) | [`remote_store.py`](hass_client/hass_client/remote_store.py) |
| Shutdown | [`__init__.py`](../homeassistant/components/sandbox_v2/__init__.py) (`_on_stop`), `manager.py` | [`sandbox.py`](hass_client/hass_client/sandbox.py) (`_run_graceful_shutdown`) |
| Test infra | — | [`testing/`](hass_client/hass_client/testing/), [`run_compat.py`](run_compat.py) |

The wire protocol constants live in two files that mirror each other
verbatim:
[`homeassistant/components/sandbox_v2/protocol.py`](../homeassistant/components/sandbox_v2/protocol.py)
and [`sandbox_v2/hass_client/hass_client/protocol.py`](hass_client/hass_client/protocol.py).
