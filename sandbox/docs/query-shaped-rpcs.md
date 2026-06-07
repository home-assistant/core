# Query-shaped RPCs — the unproxied entity-component APIs

> Status: **request/response shipped; subscriptions still open.** The two
> request/response mechanisms (the `call_service` `return_response` path for ops
> with a `SupportsResponse` service, and the generic `sandbox/entity_query` RPC
> for the service-less ones) are wired and tested — every server-side query and
> WS-only mutation below now answers with real data. What remains is the
> subscription/push primitive (the `*/subscribe` rows + the `todo` item-list
> push) and the `media_player.browse_media` media-source caveat. See
> [`../plans/plan-query-rpc.md`](../plans/plan-query-rpc.md) and
> [`../status/STATUS-plan-query-rpc.md`](../status/STATUS-plan-query-rpc.md).

## Why these don't ride the existing bridge

The entity bridge (§8 of [`ARCHITECTURE.md`](../ARCHITECTURE.md)) is
**fire-and-forget**: a proxy entity method becomes one
`services.async_call(domain, service, target=…)` over `sandbox/call_service`.
That shape can *command* the real entity but can't, on its own, **ask it a
question and get an answer back**. Every API below is a server-side query, a
subscription, or a WS-only mutation that has no service to forward through. The
request/response ones are now wired (a second `return_response` flavour of
`call_service`, plus the generic `entity_query` RPC — see §8). The
subscription-shaped commands (`weather/subscribe_forecast`,
`calendar/event/subscribe`) ride the same query methods but get only the
**one-shot fetch** — no streamed updates until the push primitive lands. The
`entity.raise_not_proxied(...)` helper is now callerless, kept for that
deferred subscription/`todo`-push work.

Two distinct primitives — the first is shipped, the second is not:

1. **Request/response RPC — SHIPPED.** Two flavours: ops that already have a
   `SupportsResponse` service ride the existing `call_service` path with
   `return_response=True` (the sandbox re-runs the real service against the real
   entity); the genuinely service-less ops cross via a generic
   `sandbox/entity_query` RPC where main sends `{sandbox_entity_id, method,
   args}`, the sandbox invokes the real entity method, and the serialised result
   (wrapped `{"value": …}`) comes back. Main rebuilds each rich return type
   (`BrowseMedia` / `CalendarEvent` / `SearchMedia` / `Segment`) with explicit
   field mapping. Covers everything except the subscriptions.
2. **Subscription / push RPC — still missing.** A `sandbox/entity_subscribe` +
   push channel for the `*/subscribe` commands (weather forecast, calendar
   events) and for pushing the `todo` item list into a proxy cache, so the
   sandbox can stream updates main re-emits to the WS client. Until it lands the
   `*/subscribe` commands get only the one-shot fetch the request/response path
   provides, and `todo` is routed to main — see the note below.

## The catalogue

Entrypoint = what a frontend/automation actually calls on main. Entity API =
the method/property the core handler invokes on the (proxy) entity. "Forwards"
means it already works one-way via a service; everything else now raises.

| Domain | Entrypoint (service / WS) | Entity API | Shape | Status |
|---|---|---|---|---|
| `calendar` | `calendar.get_events` (svc, response) | `async_get_events` | request/response | **wired** (`call_service` `return_response`) |
| `calendar` | `calendar/event/subscribe` (WS) | `async_get_events` + recurrence timer | subscription | **one-shot only** (no streamed updates) |
| `calendar` | `calendar/event/create` (WS) | `async_create_event` | command | forwards (`calendar.create_event` svc) |
| `calendar` | `calendar/event/update` (WS) | `async_update_event` | command (WS-only, no svc) | **wired** (`entity_query`) |
| `calendar` | `calendar/event/delete` (WS) | `async_delete_event` | command (WS-only, no svc) | **wired** (`entity_query`) |
| `todo` | *whole platform* | `todo_items` (property) | n/a | **routed to main** (see note) |
| `weather` | `weather.get_forecasts` (svc, response) | `async_forecast_{daily,hourly,twice_daily}` | request/response | **wired** (`call_service` `return_response`) |
| `weather` | `weather/subscribe_forecast` (WS) | `async_forecast_*` + listeners | subscription | **one-shot only** (no streamed updates) |
| `media_player` | `media_player.browse_media` (svc, response) / `media_player/browse_media` (WS) | `async_browse_media` | request/response | **wired** (`call_service` `return_response`; media-source caveat) |
| `media_player` | `media_player/search_media` (WS) | `async_search_media` | request/response | **wired** (`entity_query`) |
| `update` | `update/release_notes` (WS) | `async_release_notes` | request/response | **wired** (`entity_query`) |
| `vacuum` | `vacuum/get_segments` (WS) | `async_get_segments` | request/response | **wired** (`entity_query`) |

### The `todo` exception — routed to main, not proxied

`TodoListEntity.state` is `len(self.todo_items)`, so `todo_items` is read on
**every state write**, not just on a query. It can't raise (that would break
the state machine) and it can't block on a request/response query (it's a sync
property). The only honest fix is for the sandbox to **push** the item list
into a proxy cache so `todo_items` returns it synchronously — i.e. the
subscription/push primitive, which is out of scope this iteration.

Rather than ship a proxy whose To-do panel silently shows an empty list while
looking supported, `todo` is in `SANDBOX_INCOMPATIBLE_PLATFORMS`
(`components/sandbox/const.py`) — any integration exposing a `todo` platform
routes to main, exactly like `camera`. There is no `todo` proxy. Revisit when
the push primitive lands.

## Not in scope here (handled elsewhere)

- **`camera`** — excluded entirely by `SANDBOX_INCOMPATIBLE_PLATFORMS` (byte
  streams the channel can't ferry).
- **`todo`** — also `SANDBOX_INCOMPATIBLE_PLATFORMS` (sync-property-feeds-state
  problem above; needs a push primitive, not a query).
- **`image`** — `ALWAYS_MAIN` (non-idempotent pre-dispatch work).
- **Static metadata WS commands** — `weather/convertible_units`,
  `sensor/device_class_convertible_units`, `sensor/numeric_device_classes`,
  `number/device_class_convertible_units`. These are stateless lookups that run
  on main and never touch a sandboxed entity; nothing to proxy.

## Caveat: `media_player.browse_media` won't include media sources

On a normal install a media player's `async_browse_media` merges in the
**`media_source`** tree (local media, TTS-cached clips, etc.) by calling
`media_source.async_browse_media(self.hass, …)`. Inside the sandbox `self.hass`
is the private, isolated instance — `media_source` runs on **main**, outside
the sandbox boundary, so that call has nothing to resolve against. A sandboxed
player's browse therefore surfaces **only the player's own sources**; the
"Media Sources" branch will be empty for now. Closing this needs a cross-
boundary hook (the sandbox would have to call back into main's `media_source`),
which belongs with the same opt-in sharing work as the lockdown helpers — out
of scope for the query RPC. Document it where the browse proxy is wired so it
isn't mistaken for a bug.

## Response-returning services — a second look

`calendar.get_events`, `todo.get_items`, `weather.get_forecasts`, and
`media_player.browse_media` are registered with `SupportsResponse.ONLY`. They
dispatch to the entity method **on main** (against the proxy), so they're
covered by the request/response RPC above — but whoever designs that RPC should
confirm the service-forwarder path (`ServiceMirror`) also carries a
`ServiceResponse` back for any *integration-owned* response service, which is a
related but separate hole.
