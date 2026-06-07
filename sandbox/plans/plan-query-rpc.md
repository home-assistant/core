# Plan — Query-shaped RPCs (request/response iteration)

> Source: [`../../.claude/plans/query-rpc/interview.md`](../../.claude/plans/query-rpc/interview.md)
> · Gap catalogue: [`../docs/query-shaped-rpcs.md`](../docs/query-shaped-rpcs.md)
> · Status notes go to `sandbox/status/STATUS-plan-query-rpc.md` when work lands.

## Goal

Let sandbox proxy entities answer server-side **queries** they currently raise
`HomeAssistantError` for. Two mechanisms, no new subscription primitive this
iteration:

- **Reuse the existing `call_service` + `return_response` path** for entity
  methods that have a `SupportsResponse` service.
- **Add one generic `EntityQuery` RPC** for the genuinely service-less methods.

`todo` is **out** — already routed to main via `SANDBOX_INCOMPATIBLE_PLATFORMS`
(needs a push-cache, not a query). Subscriptions (`weather/subscribe_forecast`,
`calendar/event/subscribe`) stay raising — deferred to a later push iteration.

## Success criteria

- [ ] `calendar.get_events`, `weather.get_forecasts`, `media_player.browse_media`
      return real data through a sandboxed entity.
- [ ] `media_player/search_media`, `update/release_notes`, `vacuum/get_segments`,
      `calendar/event/update`, `calendar/event/delete` work through a sandboxed
      entity.
- [ ] A sandbox-side `HomeAssistantError` / `ServiceValidationError` /
      `BrowseError` / `SearchError` surfaces on main as the same error shape a
      local entity would raise (mirrors today's `vol.Invalid` translation).
- [ ] Channel-down / sandbox-unavailable degrades to a clean
      `HomeAssistantError`, never a hang or raw decode error.
- [ ] `uv run pytest tests/components/sandbox/` + the client suite green; proto
      drift guard passes; `uv run prek run` clean.

## The verified split

| Op | Mechanism | Return type to rebuild on main |
|---|---|---|
| `calendar.async_get_events` | service `calendar.get_events` (`return_response`) | `list[CalendarEvent]` |
| `weather.async_forecast_{daily,hourly,twice_daily}` | service `weather.get_forecasts` (`return_response`) | `list[Forecast]` (plain TypedDict — trivial) |
| `media_player.async_browse_media` | service `media_player.browse_media` (`return_response`) | `BrowseMedia` (recursive) |
| `media_player.async_search_media` | **EntityQuery** | `SearchMedia` (holds `list[BrowseMedia]`) |
| `update.async_release_notes` | **EntityQuery** | `str | None` (trivial) |
| `vacuum.async_get_segments` | **EntityQuery** | `list[Segment]` (dataclass) |
| `calendar.async_update_event` | **EntityQuery** | `None` (mutation) |
| `calendar.async_delete_event` | **EntityQuery** | `None` (mutation) |

Rule for future ops: **service path when a `SupportsResponse` service maps to
the method; `EntityQuery` only when none exists.**

---

## Phase 1 — Service-path response queries (no proto change)

The `return_response` plumbing already exists end-to-end:
`bridge.async_call_service(..., return_response=True)` →
`_raw_call_service` sets `CallService.return_response` →
sandbox `EntryRunner._handle_call_service` runs the service with
`return_response=True` and packs `CallServiceResult.response.data`
(`entry_runner.py:122`). Only the proxy + rebuild layer is missing.

- [ ] Add a `return_response` param to `SandboxProxyEntity._call_service`
      (`entity/__init__.py:164`) — pass it through to `async_call_service`, and
      when set, return `struct_to_dict(result.response.data)` if
      `result.HasField("response")` else `{}`. (Today proxies ignore the
      return; the value is the decoded `CallServiceResult` pb message.)
- [ ] **calendar** (`entity/calendar.py`): replace the `async_get_events` raise
      with a `calendar.get_events` service forward (`return_response=True`,
      `start_date_time`/`end_date_time` args) and rebuild `list[CalendarEvent]`
      from the response `events` list. Add a `_calendar_event_from_dict` helper
      (summary/start/end/description/location/uid/rrule/recurrence_id).
- [ ] **weather** (`entity/weather.py`): replace the three `async_forecast_*`
      raises with a `weather.get_forecasts` service forward (`type=<kind>`,
      `return_response=True`); the response is keyed by **sandbox** entity_id —
      unwrap `response[self.description.sandbox_entity_id]["forecast"]` and
      return it (Forecast is a plain TypedDict, no rebuild).
- [ ] **media_player** (`entity/media_player.py`): replace `async_browse_media`
      raise with a `media_player.browse_media` service forward
      (`media_content_type`/`media_content_id`, `return_response=True`) and
      rebuild `BrowseMedia` from the dict (recursive over `children`). Add a
      `_browse_media_from_dict` helper.
      **Caveat to document at the call site (and Risk #5):** a sandboxed
      player's browse will include **only its own sources** — the `media_source`
      tree it normally merges via `media_source.async_browse_media(self.hass, …)`
      is empty inside the sandbox, because `media_source` runs on main, outside
      the sandbox boundary. Not a bug; closing it needs a cross-boundary hook
      (later, with the opt-in sharing work). See the catalogue caveat.
- [ ] Confirm the service response shape on the sandbox side: `browse_media`
      service returns `BrowseMedia.as_dict()`; `get_events` returns
      `{"events": [...]}`; `get_forecasts` returns `{<entity_id>: {"forecast": [...]}}`.
      Pin each in a test fixture.

## Phase 2 — `EntityQuery` RPC primitive

Mirror the `call_service` pattern exactly (proto → codec registry → bridge
sender + error translation → sandbox handler).

- [ ] **proto** (`sandbox/proto/sandbox.proto`): add
      ```
      message EntityQuery {
        string sandbox_entity_id = 1;
        string method = 2;                       // e.g. "async_search_media"
        google.protobuf.Struct args = 3;         // kwargs, dynamic
        optional string context_id = 4;          // same wire-safe id rule as CallService
      }
      message EntityQueryResult {
        google.protobuf.Struct result = 1;       // wrapped: {"value": <return>}
      }
      ```
      Wrap the return in a `{"value": …}` struct so scalar/list/None returns are
      all representable (Struct's top level must be an object).
- [ ] Regenerate gencode: `bash sandbox/proto/generate.sh` (isolated venv, writes
      both `_proto` mirrors). Verify `sandbox/proto/check_drift.sh` passes.
- [ ] **constants**: add `MSG_ENTITY_QUERY = "sandbox/entity_query"` to both
      `homeassistant/components/sandbox/protocol.py` and
      `sandbox/hass_client/hass_client/protocol.py`.
- [ ] **registry**: add `"sandbox/entity_query": (pb.EntityQuery, pb.EntityQueryResult)`
      to `messages.REGISTRY` in **both** mirrors (`messages.py`).
- [ ] **bridge sender** (`bridge.py`): add
      `async_entity_query(*, sandbox_entity_id, method, args, context) -> Any`
      next to `async_call_service`. Build `pb.EntityQuery`, `channel.call`,
      translate errors through the existing `_translate_remote_error` /
      `ChannelClosedError` paths, and return `struct_to_dict(result.result)["value"]`.
- [ ] **sandbox handler**: register `MSG_ENTITY_QUERY` in `EntryRunner._wire`
      (`entry_runner.py:49`). Handler resolves the entity from the private hass
      by `sandbox_entity_id`, `getattr`s `method`, `await`s it with
      `struct_to_dict(args)`, wraps `{"value": _serialise(return)}` into
      `EntityQueryResult`. Raised exceptions propagate as channel error frames —
      reuse the existing `error_data` packing so `vol.Invalid`/HA errors rebuild
      on main (confirm `BrowseError`/`SearchError` map to `HomeAssistantError`).
- [ ] **proxy helper** (`entity/__init__.py`): add
      `async def _entity_query(self, method, **args)` calling
      `self._bridge.async_entity_query(...)` with `self._context`.

## Phase 3 — Wire the service-less ops onto `EntityQuery`

Replace each `raise_not_proxied(...)` with an `_entity_query` call + rebuild:

- [ ] **media_player.async_search_media** → `_entity_query("async_search_media",
      query=<SearchMediaQuery as dict>)`; rebuild `SearchMedia` (reuse the
      `_browse_media_from_dict` helper for its `result` list).
- [ ] **update.async_release_notes** → `_entity_query("async_release_notes")`;
      return the str/None directly.
- [ ] **vacuum.async_get_segments** → `_entity_query("async_get_segments")`;
      rebuild `list[Segment]` (dataclass).
- [ ] **calendar.async_update_event / async_delete_event** → `_entity_query(...)`
      forwarding uid/event/recurrence args; ignore the `None` result.
- [ ] Sandbox-side `_serialise` must handle each return: `SearchMedia.as_dict()`,
      `Segment` (dataclass → `dataclasses.asdict`), `BrowseMedia.as_dict()`.

## Phase 4 — Serialization fidelity + tests

- [ ] One serializer/deserializer per rich type, with a round-trip unit test:
      `BrowseMedia` (recursive `children`, `thumbnail`, `media_class`),
      `CalendarEvent` (rrule/recurrence_id/all-day date vs datetime),
      `SearchMedia`, `Segment`. Forecast + release_notes are plain → assert
      pass-through only.
- [ ] Extend `tests/components/sandbox/test_domain_proxies.py` (or a new
      `test_entity_query.py`) with a query case per op: stub the sandbox-side
      entity method, assert the proxy returns the rebuilt typed object.
- [ ] Error-path tests: sandbox method raises `ServiceValidationError` →
      proxy raises the translated error; channel closed → `HomeAssistantError`.
- [ ] Client-side test for the `EntityQuery` handler
      (`sandbox/hass_client/`): unknown entity_id, unknown method, method raises.

## Verification

```bash
bash sandbox/proto/check_drift.sh
uv run pytest tests/components/sandbox/ --no-cov -q
uv run pytest sandbox/hass_client/ -q
uv run prek run --files <changed>
```

## Risks / open questions (self-check)

1. **Recursive `BrowseMedia` size.** A media tree can be large; one Struct
   round-trip per browse is fine (it's user-initiated, not hot-path), but note
   it — no coalescing needed here.
2. **`as_dict()` vs constructor asymmetry.** `BrowseMedia.as_dict()` is shaped
   for the frontend (e.g. `children_media_class`, `thumbnail`), not for
   `BrowseMedia(**d)`. The rebuild helper must map fields explicitly, not
   splat. Same caution for `CalendarEvent` (dates serialise to ISO strings).
   This is the highest-effort, highest-risk part — validate with round-trip
   tests first (Phase 4 before Phase 1/3 rebuild code if needed).
3. **Why generic `EntityQuery` over typed messages?** Decided in interview:
   far fewer proto messages; the cost is serialization lives in hand-written
   `_serialise`/rebuild helpers rather than the proto schema. Acceptable for a
   handful of ops; revisit if the surface grows.
4. **Does the service path double-validate?** The sandbox re-runs the full
   `calendar.get_events`/`browse_media` service (schema + handler) against the
   real entity — that's the point (fidelity), not a bug. Confirm no main-side
   pre-validation rejects before forwarding.
5. **`browse_media` loses the media-source tree.** A sandboxed player's browse
   shows only its own sources; the `media_source`-backed "Media Sources" branch
   is empty because `media_source` lives on main, not in the sandbox's private
   hass. Known limitation, documented at the call site — needs a cross-boundary
   hook to fix (out of scope, pairs with opt-in sharing).

## Out of scope (explicit)

- Subscription/push RPC (`weather/subscribe_forecast`, `calendar/event/subscribe`,
  and the eventual `todo` item-list push that would un-block `todo`).
- Coalescing same-tick queries (mirrors the `call_service` future-opt note).
- Integration-owned `SupportsResponse` services through `ServiceMirror` — the
  related response-carry hole flagged in the catalogue; separate task.
