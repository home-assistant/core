# Running Integrations Somewhere Else
### An introduction to the Home Assistant sandbox

> Presenter notes are in blockquotes. Everything else is the slide.

---

## Slide 1 — A thought experiment

**What data do you need from an integration to represent its devices and
entities in *another* Home Assistant instance?**

Imagine the integration runs *over there*, and your instance has to look
exactly as if it ran *here*. What has to cross?

---

## Slide 2 — Surprisingly little

Three pieces of data, one channel of control:

1. **Entity state** — the current state + attributes of every entity.
2. **Entity registry entries** — unique_id, name, icon, device class,
   entity category, supported features, capability attributes.
3. **Device registry entries** — identifiers, manufacturer, model,
   connections — so entities group into devices like they always do.

And to *control* it?

4. **We call services.** `light.turn_on` with a target is already a
   serializable, remote-friendly contract. The other instance executes it
   against the real integration and the resulting state change flows back
   as data.

> This is the core insight: HA's own architecture is already
> message-shaped. State flows one way, service calls flow the other.
> In the sandbox this is exactly two messages inbound
> (`register_entity`, `state_changed`) and one outbound
> (`call_service`). A proxy entity on main holds the cached state and
> turns every method call (`async_turn_on`, …) into a `call_service`
> round-trip. 31 entity domains work this way today.

---

## Slide 3 — What about integration events?

Integrations fire domain events that automations rely on:
`zha_event`, `mqtt_message_received`, …

**We listen for events.**

- The remote side watches its own event bus.
- Events that belong to the integration (`<domain>_*`) are forwarded.
- Main re-fires them on its bus — automations trigger as if the
  integration ran locally.

> One new message type: `fire_event`. The filter is "events named after a
> domain the integration owns" — an integration that registered light
> entities or set up the `zha` entry gets `zha_*` through, nothing else.
> Important subtlety: only a *context id* crosses the wire, never
> `user_id`/`parent_id`. Main keeps a short-lived cache of every context
> it handed down and restores the original on echo — the remote side can
> never fabricate attribution.

---

## Slide 4 — What about integration actions?

Integrations also *register* their own services: `zha.permit`,
`shopping_list.add_item`, …

**We register the action on main and forward the calls.**

- The remote side notices a service registration and tells main.
- Main registers a thin forwarder under the same `domain.service`,
  including the (best-effort) serialized validation schema.
- A user or automation calls it on main → the call is forwarded → the
  real handler runs remotely → **the response is forwarded back**
  (`SupportsResponse` services included).

> Same `call_service` channel as entity control — one path, both
> directions of meaning. The schema serialization is an optimisation:
> if a schema is too exotic to serialize, main registers without one and
> the remote side still validates. A service is never dropped because its
> schema didn't survive the trip.

---

## Slide 5 — The awkward ones: entities you *ask questions*

Some entities aren't just state + commands. They have methods that
**return data**:

- `calendar.async_get_events(start, end)` — the calendar panel
- `weather.async_forecast_daily()` — forecasts
- `media_player.async_browse_media()` — the media browser
- `update.async_release_notes()`

A cached state dict can't answer these.

---

## Slide 6 — Entity RPC

Two-tier solution, in order of preference:

1. **If a `SupportsResponse` service exists, use it.**
   `calendar.get_events`, `weather.get_forecasts` already ride the
   service-call-with-response path from slide 4. No new machinery.
2. **Otherwise: a generic `entity_query` RPC.** Names the entity, the
   method, and the kwargs; the remote side calls the real method and
   returns the serialized result; main rebuilds the rich return type
   (`CalendarEvent`, `BrowseMedia`, …).

> The lesson: keep the generic paths fat and the special cases thin.
> Most "special" entity APIs turned out to be one of two shapes —
> a service with a response, or a plain method call — so two mechanisms
> cover calendar, weather, media_player, update, and vacuum.
> Still open: *subscriptions* (`weather/subscribe_forecast` streaming
> updates) and `todo`, whose panel reads a sync property that needs a
> pushed item-list cache. Honest limits, documented, routed around.

---

## Slide 7 — Now make "another instance" a sandbox

Everything so far said "another instance". Now the payoff: that other
instance is an **isolated subprocess** — a private, minimal HA running
just the integration, talking to main over a single protobuf channel.

```
main HA  ──  register_entity / state_changed / fire_event / register_service  ──▶
        ◀──  call_service / entity_query / flow RPCs / store IO  ──  sandbox
```

- Config flows forward too: the real `ConfigFlow` runs in the sandbox,
  main renders its forms and **owns the resulting `ConfigEntry`**.
- The sandbox is locked down: it sees none of main's state, holds no
  credential, and can't author a `Context`. Main decides the routing.

---

## Slide 8 — One domain lives fully in one sandbox

The unit of placement is the **integration domain** — never split.

- All of `hue` — its config entries, entities, services, events —
  lives in exactly one sandbox group.
- A classifier decides at flow-creation time: built-ins → the
  `built-in` group, custom/HACS code → the `custom` group, and a
  short deny-list (audio platforms, broad-reading helpers like
  `template`) stays on `main`.
- The decision is persisted on the entry (`ConfigEntry.sandbox`) and
  made by **main only** — a sandbox cannot choose where it runs.

> Why never split? The integration's internals assume one process: its
> coordinator, its entities, its services all share objects. The bridge
> crosses HA's *public* contracts (state, services, events), not Python
> object graphs.

---

## Slide 9 — Sandboxes are ephemeral

A sandbox holds **no persistent state**. Kill it, wipe it, restart it —
nothing is lost:

- **Config** is pushed on every `entry_setup`.
- **Storage** (`Store` IO) transparently routes to main, which persists
  it under `.storage/sandbox/<group>/`.
- **Restore state** is snapshotted to main on graceful shutdown and
  warm-loaded on the next boot.
- Even the **integration code** is fetched at startup — custom code
  arrives as a sha-pinned tarball; built-ins ship with the runtime.

So a sandbox is wipe-and-restart safe, and in principle could run
anywhere a channel can reach — a container today, another machine later.

---

## Slide 10 — The whole picture

| You need… | The sandbox crosses it as… |
|---|---|
| Entities & devices on main | `register_entity` (registry + device info) + `state_changed` |
| Control | `call_service` (proxy entity methods) |
| Integration events | `fire_event`, domain-gated, context restored on main |
| Integration actions | `register_service` + forwarded calls, responses included |
| Question-shaped APIs | response services, else generic `entity_query` |
| Config flows | forwarded; main owns the entry |
| Persistence | none — storage, restore state, config, even code come from main |

**One unified instance for the user. Untrusted code in a disposable box.**

> Closing beat: nothing here required inventing a new model — the
> sandbox is HA's existing contracts (state machine, service registry,
> event bus, config entries, storage) made remote, one seam at a time.
