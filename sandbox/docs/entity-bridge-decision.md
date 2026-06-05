# Entity-bridge decision (Phase 1)

> **Decision:** adopt **Option B — action-call forwarding** for the sandbox entity
> bridge. The proxy entity translates each entity method into a standard
> `services.async_call("<domain>", "<service>", target={"entity_id": [...]})`
> round-trip over the shared `sandbox/call_service` transport.

This document records the spike (`sandbox/hass_client/hass_client/spike/`,
tests at `tests/components/sandbox/test_spike.py`), the numbers it
produced, and the trade-offs that drove the call.

## What the spike measured

The spike runs **two `HomeAssistant` instances in the same process**, joined
by an in-process JSON transport
(`hass_client.spike.transport.InProcessTransport`). The transport
`json.dumps`/`json.loads`-es every message and pushes it through an
`asyncio.Queue` so every round-trip pays the cost of one loop yield plus
serialization (no network — that's identical between options and would only
add noise).

Both options share that transport. The only differences between them are:

- **Option A — method-forward RPC.** A bespoke
  `sandbox/entity_method_call` carries `(entity_id, method, kwargs)`. The
  sandbox-side handler does `getattr(entity, method)(**kwargs)`.
- **Option B — action-call forwarding.** A generic
  `sandbox/call_service` carries `(domain, service, target, service_data)`.
  The sandbox-side handler just calls `hass.services.async_call(...)`. The
  sandbox's normal service dispatcher resolves the target and invokes
  `async_turn_on` on the real entity.

The spike installs 100 `SyntheticLight` entities on the sandbox side and 100
proxy entities on the main side, assigns the proxies to an area, then
repeatedly calls `light.turn_on` with `target={"area_id": ...}`. Each
iteration toggles all 100 lights on and resets via `turn_off`.

## Numbers

Five runs of `test_report_comparison`, 100-entity area call, 5 iterations
each:

| Option | Median (ms) | Min (ms) | Max (ms) | RPCs / call | Bytes / iteration |
|:------:|------------:|---------:|---------:|------------:|------------------:|
| A      | ~46         | ~44      | ~50      | 100         | ~17.8 KB          |
| B      | ~64         | ~60      | ~70      | 100         | ~20.7 KB          |

Per-entity round-trip cost:

- **A:** ~0.46 ms / entity (just the RPC dispatch + a direct `await
  entity.async_turn_on(**kwargs)`).
- **B:** ~0.64 ms / entity (~0.18 ms more — the extra cost is HA's full
  service handler on the sandbox side: target resolution, schema validation,
  per-entity dispatch).

Both options send exactly one RPC per proxied entity per call. The byte
delta comes from Option B's richer payload (`target` + nested `entity_id`
list + `service_data`).

## Lines of glue per new domain

Counted from the spike's `light` proxies (whole class, including docstrings
and properties):

| Option | Proxy class LOC | Shared bridge LOC (one-time, not per-domain) |
|:------:|----------------:|---------------------------------------------:|
| A      | 42              | 37                                           |
| B      | 48              | 45                                           |

Per-domain cost is essentially the same — both options ultimately need the
proxy class plus its cached state/capability properties (the same
`brightness`/`color_mode`/`supported_color_modes`/… fan-out v1 has). The 6-
line delta is the slightly bigger `target=` dict construction inside each
method body and is noise compared to the capability-property surface a real
proxy needs.

## Why Option B

1. **Smaller protocol surface — and the channel is on the critical path
   regardless.** Phase 6 has to build a generic `sandbox/call_service`
   channel anyway, both to mirror sandbox-registered services back to main
   *and* so main can invoke services provided by sandboxed integrations.
   Option B reuses that channel for entity calls; Option A adds a second
   channel that does the same job for the entity-only subset. We get no
   protocol savings by deferring B — we just postpone consolidating onto
   the channel we have to build either way.
2. **Behaviour parity for free.** Anything HA's own service handler does —
   target resolution, schema validation, entity filtering, color-mode kwarg
   filtering (`filter_turn_on_params`), response-data routing for services
   that return values — works for the proxy without re-implementing it.
   Option A has to keep its dispatcher in step with whatever HA's service
   layer adds.
3. **Per-domain glue is identical.** 42 vs 48 lines means the maintenance
   burden of adding a new domain is the same either way. The proxy class is
   the bulk of the work, and that doesn't change.
4. **Latency cost is small and we already plan to batch.** ~0.18 ms/entity
   extra. The plan's existing Risk note already says: *"if either bridge
   option exceeds ~50 ms for 100 entities, plan a batching layer in Phase
   5."* Option B is over that line (~64 ms) in-process, so batching is on the
   table regardless. A real websocket will add more latency on top of both
   options — the *relative* cost stays the same.
5. **One fewer dispatcher to maintain.** Option A's sandbox-side
   `_handle_entity_method` is small but real, and it would need extending
   each time we add a new entity method shape (e.g., custom entity services
   registered with non-trivial schemas). Option B inherits HA's full surface
   and stays in lockstep with it.

## Trade-offs worth recording

- **Error paths differ slightly.** Option B's call goes through HA's
  service-call schema. A bad kwarg comes back as a `vol.Invalid` from the
  schema layer rather than as an `AttributeError`/`TypeError` from the
  entity method. The bridge needs to translate these so the proxy raises
  the same exception types it would have raised locally.
- **Non-entity services from sandboxed integrations are unaffected.** Option
  B already routes everything through `services.async_call`; whether the
  registered handler is an entity service or a free service is transparent
  to the bridge. Option A would have needed *both* the entity_method RPC
  *and* a separate generic service-call path; B collapses these into one.
- **Spike vs reality.** The spike's transport is in-process. A real
  websocket adds aiohttp framing + TCP RTT, identical for both options. The
  ~0.18 ms/entity delta should hold; the absolute numbers will be larger
  and dominated by transport latency once a real connection is in the loop.
- **The wire is JSON for both options.** `kwargs` must survive
  `json.dumps` (with HA's encoder, so `datetime` rides as ISO strings,
  enums as their values, etc.). Anything that doesn't — `bytes`,
  generators, file handles, in-memory `BrowseMedia` trees with cyclic
  references — fails on the wire under *either* option. That's an entity-
  method-signature constraint, not a bridge-protocol one.

## Where neither bridge option is enough

Some integrations have **non-idempotent service handlers**: the handler
does meaningful work (resolution, I/O, object construction) *before*
calling the entity method, and the entity method receives kwargs whose
type signature doesn't match the registered service schema. For these,
the proxy entity intercepts too late — by the time the proxy's method
runs on main, the handler has already done the work, and Option B can't
re-issue `services.async_call` with the post-handler kwargs because they
no longer satisfy the service schema. Option A *can* sometimes limp by
shipping the post-handler objects over the wire (e.g. file paths work
because parent and child share a filesystem), but only with bespoke per-
integration glue.

Canonical example, from `homeassistant/components/ai_task/task.py:43-95`:

- Service schema accepts `attachments: [{media_content_id: str,
  media_content_type: str}, ...]`.
- `_resolve_attachments` inside the service handler walks each attachment,
  either fetches bytes from a camera/image entity (deny-listed!) or calls
  `media_source.async_resolve_media`, writes the bytes to a temp file, and
  builds `Attachment(media_content_id=..., mime_type=..., path=Path(...))`.
- The entity method `_async_generate_data` receives the resolved
  `Attachment` list — `Path` objects, not the original `media_content_id`
  strings.

If `ai_task` were sandboxed:

- **Option B**: proxy gets the resolved list, tries to re-issue
  `services.async_call("ai_task", "generate_data", service_data={
  "attachments": [Attachment(...)]})`, schema rejects it.
- **Option A**: proxy ships the `Attachment` list as a dict (with `Path`
  coerced to `str`), sandbox reconstructs. The path works *because* the
  parent and child share a filesystem, but the upstream resolution call
  into camera/image still needed to succeed on main, and camera/image
  entities are deny-listed and only available on main. So the bytes had
  to be fetched there anyway — Option A's "advantage" here is mostly that
  it lets us paper over a bigger architectural gap, not that it solves it.

**Resolution path.** Two complementary directions, neither in scope for
this phase:

1. **Service-handler-level interception** for integrations where the
   service handler is non-idempotent. The bridge would intercept the
   service call *before* the handler runs and forward the raw service
   data to the sandbox; the sandbox-side handler runs against sandbox-
   local entities. This is a small extension of the Option B channel —
   essentially the same as Phase 6's main→sandbox service mirroring,
   pointed in the other direction.
2. **Make individual integrations sandbox-aware** so they cooperate with
   the bridge rather than fight it. `ai_task` is the canonical first
   candidate: the service handler could detect that the target entity
   lives in a sandbox and route the raw attachment dicts there before
   resolution, so resolution happens once on the side that's going to
   consume the result. Same shape for any future integration whose
   service handler does expensive pre-dispatch work.

**Immediate consequence in this phase**: `ai_task` and `image` are added
to `ALWAYS_MAIN` (alongside the existing `script`/`automation`/`scene`/
`cloud`). `image` joins because its entities expose bytes-returning
methods that downstream integrations (like `ai_task`) need to call
locally; if `image` itself ran in a sandbox, those calls would fall over
the same byte-channel gap that already deny-lists `camera`. `assist_satellite`,
`camera`, `stt`, `tts`, `conversation`, `wake_word` remain in
`SANDBOX_INCOMPATIBLE_PLATFORMS` (the platform-shape deny list) because
the issue is what *their* entity methods return, not what calls them.

## Action items folded into the remaining plan

- **Phase 5 (entity bridge):** build the proxy classes against the shared
  `sandbox/call_service` channel. Mark Option A as discarded in
  `plan.md`'s "Open architectural choice".
- **Phase 5 (entity bridge):** introduce the fan-out batching helper
  flagged in the plan's Risks section — proxy entities collected during one
  service call should be coalesced into a single `sandbox/call_service`
  carrying a multi-entity target, so a 200-light area call pays one RPC,
  not 200.
- **Phase 6 (service & event mirroring):** the same `sandbox/call_service`
  channel built here is the one used for arbitrary main→sandbox service
  forwarding; no new RPC type required.
- **Phase 5 / Phase 6:** add a small exception-translation layer on the
  sandbox side so service-handler errors come back as the exception types
  the proxy entity methods originally raised.
- **Phase 2 (classifier):** `ai_task` and `image` are added to
  `ALWAYS_MAIN` immediately (see `homeassistant/components/sandbox/
  const.py`). The classifier test in Phase 2 must cover both — and
  ideally a parameterised case that asserts every domain in `ALWAYS_MAIN`
  routes to main without needing manifest inspection.
- **Future (post-Phase 11):** spec out service-handler-level interception
  for non-idempotent handlers, and/or a "sandbox-aware integration" hook
  so `ai_task` (and the next integration that fits the pattern) can
  delegate attachment-style resolution to the sandbox side.

## Reproducing the numbers

The spike harness (`sandbox/hass_client/hass_client/spike/` and
`tests/components/sandbox/test_spike.py`) was **removed once Option B was
chosen and shipped** — it was a one-off bake-off, not part of the product.
The numbers above are preserved here as the decision record; recover the
harness from git history if you ever need to re-run it.
