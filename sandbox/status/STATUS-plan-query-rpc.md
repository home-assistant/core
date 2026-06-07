# STATUS — plan-query-rpc (request/response query RPCs)

**Done.** All four phases landed; both suites green, proto drift guard clean,
prek clean on every changed file. Every server-side query and WS-only mutation
entity API the fire-and-forget bridge couldn't express now answers with real
data through a sandboxed entity. Deferred (unchanged): the subscription/push
primitive and the `todo` platform. Not pushed — the orchestrator pushes.

## Commits

| SHA | Phase | What |
|---|---|---|
| `98e63bc133e` | 1 | Service-path response queries (calendar/weather/media_player) + JSON-safe sandbox response + rebuild helpers + round-trip tests |
| `33dab107793` | 2 | Generic `EntityQuery` RPC primitive (proto + both `_pb2` mirrors, constants, registry, bridge sender, sandbox handler, proxy helper) |
| `e5f2f8f932c` | 3 | Wire the service-less ops onto `EntityQuery` (search / release_notes / segments / calendar update+delete) |
| `21788fd8156` | 4 | Serialization round-trips + per-op proxy tests + error paths + client-side handler tests |
| `6791c64d59b` | docs | query-shaped-rpcs.md / ARCHITECTURE / OVERVIEW / CLAUDE updated to "implemented" |

Five logical commits, each leaves the tree green. No `--no-verify`; pre-commit
passed on every commit.

## What shipped per phase

### Phase 1 — service-path response queries (no proto change)
- `SandboxProxyEntity._call_service` grew a keyword-only `return_response` flag
  that decodes the `CallServiceResult.response` Struct into a dict (`{}` when
  the sandbox sent no response).
- `calendar.async_get_events` → `calendar.get_events` service
  (`return_response=True`, `start_date_time`/`end_date_time` as ISO strings);
  rebuilds `list[CalendarEvent]` via `_calendar_event_from_dict` (explicit
  field map, ISO date-vs-datetime parse). Unwraps the entity_id-keyed response.
- `weather.async_forecast_{daily,hourly,twice_daily}` → `weather.get_forecasts`
  service (`type=<kind>`); `Forecast` is a plain TypedDict, returned verbatim
  after unwrapping `response[sandbox_entity_id]["forecast"]`.
- `media_player.async_browse_media` → `media_player.browse_media` service;
  rebuilds the recursive `BrowseMedia` via `_browse_media_from_dict` (explicit
  field map — not a `**dict` splat — float/int coercion).
- **Sandbox side:** `EntryRunner._handle_call_service` now runs the service
  response through the `as_dict`-aware JSON encoder (`json_bytes` →
  `json_loads`) before packing the Struct. This was **required, not optional**:
  the `media_player.browse_media` entity service returns
  `{entity_id: BrowseMedia}` — a live object protobuf's `Struct.update` rejects.
  The encoder yields the exact `as_dict()` wire shape main rebuilds from, and is
  a no-op for the already-plain calendar/weather dicts.

### Phase 2 — `EntityQuery` RPC primitive
- proto: `EntityQuery {sandbox_entity_id, method, args, context_id}` +
  `EntityQueryResult {result}` (return wrapped `{"value": …}` so scalar / list /
  None are representable). Regenerated via `sandbox/proto/generate.sh` into both
  `_pb2` mirrors; drift guard passes.
- `MSG_ENTITY_QUERY = "sandbox/entity_query"` + REGISTRY entry added to **both**
  `protocol.py` / `messages.py` mirrors.
- `SandboxBridge.async_entity_query`: builds the request, remembers the context
  before its id is reduced to a wire value, translates `ChannelRemoteError` /
  `ChannelClosedError` through the existing paths, unwraps `{"value": …}`.
- `EntryRunner._handle_entity_query`: resolves the entity on the private hass
  (`_resolve_entity` via `DATA_INSTANCES`), `getattr`s + awaits the method with
  the decoded kwargs, serialises the wrapped return through the same JSON
  encoder; raised exceptions propagate as channel error frames.
- `SandboxProxyEntity._entity_query` is the proxy-side companion to
  `_call_service`.

### Phase 3 — wire the service-less ops
- `media_player.async_search_media` → `_entity_query("async_internal_search_media",
  …)` + `_search_media_from_dict` (reuses the BrowseMedia helper).
- `update.async_release_notes` → `_entity_query("async_release_notes")` (str/None).
- `vacuum.async_get_segments` → `_entity_query("async_get_segments")` +
  `_segment_from_dict` (dataclass).
- `calendar.async_update_event` / `async_delete_event` → `_entity_query(…)`
  (None result).

### Phase 4 — serialization fidelity + tests
- Round-trip rebuild unit tests for `CalendarEvent` (timed / all-day /
  recurring), `BrowseMedia` (recursive), `SearchMedia`, `Segment` — no wire in
  the loop (Risk #2, written alongside the helpers).
- Per-op proxy tests over a wired bridge + in-memory channel pair: each query
  asserts the rebuilt typed object and the forwarded service/method + args.
- Error paths: sandbox-side `ServiceValidationError` → translated
  `HomeAssistantError` on main; closed channel → clean `HomeAssistantError`.
- Client-side `EntityQuery` handler: method invocation, kwarg passing, unknown
  entity_id, unknown method, raising method (exception type on the error frame).

## Deferred (out of scope, unchanged)
- **Subscription / push RPC.** `weather/subscribe_forecast` and
  `calendar/event/subscribe` ride the now-working one-shot query methods but get
  no streamed updates. `todo` stays in `SANDBOX_INCOMPATIBLE_PLATFORMS` (routed
  to main) — its sync `todo_items` property feeds `state`, so it needs the push
  cache, not a query. No subscription primitive was implemented.
- **`media_player.browse_media` media-source tree.** A sandboxed player's browse
  surfaces only its own sources; the `media_source` tree runs on main, outside
  the boundary. Documented at the call site + in the catalogue; needs a
  cross-boundary hook (pairs with opt-in sharing).
- **Integration-owned `SupportsResponse` services through `ServiceMirror`** —
  the related response-carry hole flagged in the catalogue; separate task.

## Deviations / decisions
- **Search targets `async_internal_search_media`, not `async_search_media`.**
  The plan literally wrote `_entity_query("async_search_media", query=<dict>)`,
  but `async_search_media` takes a `SearchMediaQuery` object — the generic
  handler splats kwargs, so a dict would break it. Forwarding to
  `async_internal_search_media` (which rebuilds the query from flat kwargs on
  the sandbox side) keeps the query as plain JSON and is correct. The proxy
  sends `media_filter_classes` as their `MediaClass` string values; `MediaClass`
  is a `StrEnum`, so string/enum membership comparisons interoperate — the
  simplest defensible choice for a rarely-used arg.
- **JSON-safe response coercion added to the sandbox handler** (Phase 1). The
  plan framed Phase 1 as "no plumbing change", but `browse_media`'s object
  response forced this; it's a minimal, encoder-reuse change, not new plumbing.
- **`entity.raise_not_proxied` is now callerless** but kept defined + exported.
  It remains the documented mechanism for the still-deferred subscription /
  `todo`-push work; removing then re-adding exported API was judged worse churn
  than leaving the small documented seam.
- **Error mapping for `BrowseError` / `SearchError`.** These are
  `HomeAssistantError` subclasses; `_translate_remote_error` has no explicit
  case, so they surface via the generic fallback as `HomeAssistantError`
  (preserving the "is a HomeAssistantError" contract) — same shape a local
  entity raise would present to the WS/service framework.

## Verification (all pass)

```
$ bash sandbox/proto/check_drift.sh
sandbox proto drift guard: gencode matches sandbox.proto.

$ uv run pytest tests/components/sandbox/ --no-cov -q
219 passed, 2 warnings in 8.10s

$ uv run pytest sandbox/hass_client/ -q
87 passed, 1 warning in 0.57s

$ uv run prek run --files <every changed file>
ruff check / ruff format / codespell / prettier / mypy / pylint ... Passed
```
