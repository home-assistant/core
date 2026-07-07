# Brainstorm: Sandbox v2 — next batch of protocol & lockdown changes

> Captured from `/phx:brainstorm` (adapted to this Python/Home Assistant repo).
> Topic: seven proposed changes to the Sandbox v2 subsystem
> (`homeassistant/components/sandbox_v2/` on main + `sandbox_v2/hass_client/`
> client library). Phases 0–20 are complete; this is post-Phase-20 work.

## Current-state grounding (verified against code, 2026-05-28)

Transport today: JSON-line frames over **stdin/stdout** (`channel.py`, both
sides). Frame shapes: call `{id,type,payload}`, response `{id,ok,result|error,
error_type}`, push `{type,payload}`. One sandbox subprocess per **group**
(`built-in`, `custom`, `main`); classifier in `classifier.py` routes by
system / `ALWAYS_MAIN` / incompatible-platform / built-in-vs-custom.

Sharing: **Phase 20 deleted the entire `share_*` surface.** Nothing is shared
today — every group is locked down (sandbox sees only its own
states/entities/services/events). The *plan* to re-introduce sharing
(`docs/design-share-states.md`) defaults `built-in` and `main` to all-on,
`custom` to all-off. **Point 1 reverses that plan: lock `built-in` down too.**

## The seven points — ask vs. reality

### 1. Lock `built-in` down like HACS; list integrations that break → main
- **Reality:** sharing is already all-off post-Phase-20. The live decision is
  to *not build* the `built-in = share-on` default in `design-share-states.md`,
  and instead treat built-in like custom (no cross-integration state / entity
  registry / area access).
- **Gap / deliverable:** an enumerated list of integrations that depend on
  reading *other* integrations' states/entities/areas, with a one-line "why"
  each, plus whether they move to `ALWAYS_MAIN` or are simply unsupported in a
  sandbox. Candidate breakers (to be verified): template & template helpers,
  group, min_max, statistics/trend/threshold/derivative/integration/
  utility_meter/history_stats, alert, schedule, anything that targets/reads by
  area, anything iterating `hass.states` or the entity registry across domains.
  `script`/`automation`/`scene` are already `ALWAYS_MAIN`.
- **Note:** this is a research/survey task; compat sweep artifacts
  (`COMPAT*.csv`, `BACKLOG_FAILURES.json`, `categorize_failures.py`) likely
  already carry signal for which integrations fail under lockdown.
- **RESEARCH DONE** → see `research/builtin-lockdown-breakage.md`. Headlines:
  (1) compat sweep gives no signal — it already ran fully isolated (share
  consumer never existed), so static analysis is authoritative; (2) all eight
  `system`-type aggregators (energy, logbook, history, recorder, zone,
  google_assistant, alexa, default_config) are **already** routed to main by
  classifier rule 1 — non-issues; (3) the real breakage set is **config-entry
  helpers** that classify into `built-in`: ~15 source-entity helpers
  (min_max, statistics, trend, threshold, derivative, integration,
  utility_meter, filter, mold_indicator, bayesian, generic_thermostat,
  generic_hygrostat, switch_as_x, history_stats, proximity) + 3 broad readers
  (template, group, homekit); (4) YAML-only `prometheus`/`alert` probably stay
  on main already (verify router.py). **New sub-fork:** Category-A helpers →
  blanket `ALWAYS_MAIN` (simple, but guts the helper experience) vs. a
  **narrow opt-in** (helper declares source entity_ids; sandbox proxies just
  those) which doubles as a scoped first version of the share-states consumer.

### 2. `--group` → `--name` on `python -m hass_client.sandbox_v2`
- **Reality:** `__main__.py` exposes `--group` (required), forwarded to
  `SandboxRuntime(group=...)`. "group" terminology is pervasive internally
  (classifier, manager, bridge, auth user names "Sandbox v2: built-in", store
  dir `…/sandbox_v2/<group>`, protocol docs).
- **Decision:** rename only the CLI flag (`--name`, keep internal `group`), or
  rename the whole concept group→name everywhere? User's stated intent is the
  CLI ergonomics ("easier to understand"), so leaning CLI-flag-only.
- **Side note:** user wrote `python -m hass_client.sandbox`; actual module is
  `hass_client.sandbox_v2`. Out of scope unless we also drop the `_v2`.

### 3. Protobuf transport over websocket / unix socket (replace stdin/stdout)
- **Reality:** `Channel` already abstracts read/write; encoding is JSON-line,
  connection is stdio (`_open_stdio_channel`). A sandbox→main **websocket** is
  already on the roadmap (auth-scoping doc, design-share doc) but unbuilt.
- **Tension:** the payloads are *highly dynamic* — serialized voluptuous
  schemas (list-of-dicts), arbitrary `device_info`, arbitrary `service_data`,
  capability attrs, arbitrary state attributes. Protobuf's value is static
  typing + codegen; carrying this dynamic data forces `Struct`/`Any`, which
  discards most of that value while adding a `.proto` build step + runtime dep.
  Two *separable* asks are bundled here: (a) **multiple transports**
  (unix socket, websocket) — achievable by abstracting Transport from codec;
  (b) **protobuf encoding** — orthogonal, debatable ROI for dynamic payloads.
- **Open:** do protobuf + transports together, or land pluggable transports
  (keep JSON) now and gate protobuf on a measured need?

### 4. `data_schema` must survive the config flow (voluptuous_serialize)
- **Reality: already implemented.** Sandbox `serialize_schema()` uses
  `voluptuous_serialize.convert(..., cv.custom_serializer)`; main
  `reconstruct_schema()` rebuilds a `vol.Schema` for rendering + coarse
  validation. The real validator stays in the sandbox.
- **Gap:** the round-trip is **lossy**. On serialize failure the sandbox sets
  `_has_data_schema` and main renders **schema-less**. `reconstruct_schema`
  maps selectors / sections / constants / datetime to a `_passthrough`
  validator and only handles string/int/float/bool/select precisely. So forms
  with selectors lose their selector type on the frontend re-render.
- **Decision:** is the ask "make survival lossless (carry the full serialized
  selector form so the frontend re-renders faithfully)" — i.e. fix the
  passthrough/`_has_data_schema` fallbacks — or just "confirm it's wired"?

### 5. Add unique_id to config flow; prefix unique IDs on main with domain
- **Reality (config-flow half): already implemented.** `_apply_remote_context`
  mirrors the sandbox flow's `unique_id` onto main's proxy flow via
  `async_set_unique_id` (drives duplicate detection / abort).
- **Reality (entity half): NOT prefixed.** `entity/__init__.py:44` sets
  `self._attr_unique_id = description.unique_id` verbatim. All proxy entities
  register under the shared `sandbox_v2` platform, so two *different*
  integrations in the same group that pick the same `unique_id` collide on
  main's entity registry.
- **Gap / decision:** prefix proxy-entity unique_ids with the source
  integration domain (e.g. `<domain>:<unique_id>`) to namespace them. Also
  consider prefixing the **config-entry** unique_id similarly. Need to confirm
  prefix format and migration for already-registered proxy entities.

### 6. Allow `register_entity` repeatedly to update entity/device info
- **Reality:** `register_entity` fires **once** per entity (`self._registered`
  set); afterwards only state pushes go out. **Neither side listens for
  `EVENT_ENTITY_REGISTRY_UPDATED` or `EVENT_DEVICE_REGISTRY_UPDATED`.** So
  post-registration changes to name / device_info / capabilities / category
  never reach main. Main's `_handle_register_entity` is **not** idempotent for
  re-register — it builds a fresh proxy and calls `async_add_entities` again
  (device `async_get_or_create` is idempotent; the entity add is not).
- **Gap:** (a) client listens to entity+device registry updated events and
  re-sends an update; (b) main handler upserts an existing proxy (update attrs
  / device link in place) rather than double-adding.

### 7. Reconstruct `vol.Invalid` instead of mapping to `TypeError`
- **Reality:** `_translate_remote_error` maps `Invalid`/`MultipleInvalid` →
  `TypeError(msg)`. The wire error frame carries only `error` (str) +
  `error_type` (class name) — **`vol.Invalid.path` and the MultipleInvalid
  child list are lost.**
- **Gap:** enrich the error frame to carry structured voluptuous data (path,
  error_message, child errors), and reconstruct a real `vol.Invalid` /
  `vol.MultipleInvalid` on main so callers get the correct type + path.
  Couples with point 3 (a richer protocol makes this clean).

## Themes
- **Transport rewrite** — point 3 (largest, most architectural).
- **Protocol fidelity** — points 4, 5, 7 (schema survival, unique_id
  namespacing, structured errors). All "make the wire carry faithful data."
- **Lifecycle correctness** — point 6 (idempotent / updatable registration).
- **Security posture** — point 1 (drop built-in sharing; enumerate fallout).
- **Ergonomics** — point 2 (CLI flag rename).

## Coverage
| Dim | Score | Notes |
|-----|-------|-------|
| What | 2/2 | Seven concrete changes, verbs clear |
| Why | 1/2 | Implied (security, fidelity, ergonomics); point-3 protobuf rationale unstated |
| Scope | 1/2 | Bundle vs split undecided; point-1 deliverable (list-only vs implement) undecided |
| Where | 2/2 | Exact files/functions identified |
| How | 1/2 | Protobuf-vs-transports split, prefix format, lossless-schema approach open |
| Edge | 1/2 | Migration of existing proxy unique_ids; MultipleInvalid nesting; cross-integration collisions noted |
| **Total** | **8/12** | Sufficient to proceed; three forks need a steer |

## Decisions (resolved 2026-05-28)
- **A. Transport → do protobuf.** The "dynamic payload" objection was wrong:
  `device_info` (DeviceInfo TypedDict) and entity descriptions
  (`SandboxEntityDescription`) have **known, fixed fields** and model cleanly
  as protobuf messages. Only the **serialized voluptuous schema** and
  **`service_data`** are genuinely arbitrary → those use
  `google.protobuf.Struct` / `Any` as a targeted escape hatch. Protobuf goes
  with the new transport layer (stdio + unix socket + websocket). This is its
  own effort, separate from the fidelity batch.
- **B. Point 1 → research the breakage list first.** Deliverable: enumerated
  list of integrations that break under built-in lockdown (no cross-integration
  state / entity registry / area access), each with a one-line why and a
  recommendation (ALWAYS_MAIN / unsupported / helper-class handling). Mine
  compat artifacts + code analysis before deciding ALWAYS_MAIN moves.
- **C. Packaging → split.** Plan 1 = protocol-fidelity + ergonomics batch
  (#2 rename, #4 lossless schema, #5 unique_id prefix, #6 idempotent register,
  #7 vol.Invalid reconstruction). Plan 2 = transport/protobuf rewrite (#3).
  Point 1 proceeds as its own research → decision track.

## Next action
Run the Point-1 breakage research (this cycle), then return to the decision
point to choose: plan the fidelity batch, plan the transport rewrite, or
deepen research.

## Status (2026-05-28)
- Point-1 research → `research/builtin-lockdown-breakage.md` (done).
- Fidelity batch (#2,4,5,6,7) → `plan-fidelity-batch.md` (done).
- Transport + protobuf rewrite (#3) → `plan-transport.md` (done). Three-layer
  Channel/Codec/Transport design, protobuf `Frame` + typed messages with
  Struct/ListValue escape hatches. **Decided:** typed protobuf handlers (no
  dict adapters); websocket deferred to the share-states work. Effort =
  T1 (framing seam) → T2 (protobuf) → T3 (unix socket) → T5 (cleanup).

## Additional asks (2026-05-28, follow-up message)
- **Remove Sandbox v1** → `plan-v1-removal.md`. Footprint verified clean (no
  external refs). Caveat: contradicts the documented "v1 stays until v2 ships a
  stable release" gate — user's explicit call. **Destructive — needs go-ahead
  before executing.**
- **Dockerfile for testing the hass_client** → `plan-docker.md`. Forward-looking:
  a containerised sandbox really needs the deferred websocket transport; usable
  now via unix-socket-over-shared-volume.
- **Stateless sandboxes / push integration source** → `plan-ephemeral-sources.md`.
  entry_setup carries an `integration_source` (builtin vs git url+sha); sandbox
  fetches custom (HACS) code at startup → no persistent code state. Key open
  fork: how core learns the git source without depending on HACS (lean: a
  registered resolver hook). Pairs with the deferred WS transport + Docker.

## Cross-cutting closing steps
- **Phase D (per plan):** ensure internal dev docs are up to date — fix
  current-state docs, leave historical `STATUS-phase-*` intact. Defined in
  `plan-v1-removal.md`.
- **Phase E (batch-level, once all phases land):** finalize the broadcast
  digest `whats-changed.md` (drafted, audience-grouped, per-phase checkboxes)
  and publish it as `sandbox_v2/CHANGES.md` so updates can be announced fast.
