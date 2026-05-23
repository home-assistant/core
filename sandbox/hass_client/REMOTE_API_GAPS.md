# Remote API Gaps In Home Assistant Core

This note captures the Home Assistant APIs that are still missing, or not strong enough, to make `hass-client` a perfect remote implementation of `hass`.

It is intentionally not a `hass-client` TODO list. Some features below already exist in Home Assistant and just need to be consumed by the client. The focus here is the gap in Home Assistant core itself.

## Biggest Gaps

### 1. Remote entity ownership API

This is the main blocker.

Home Assistant exposes:

- websocket state subscriptions
- service calls
- raw state writes through `/api/states/<entity_id>`

What it does not expose is a public API to let an external process behave like a real integration platform that owns entities. A complete remote API needs operations to:

- register a remote entity
- update entity state through the entity model instead of raw state injection
- remove an entity
- attach integration metadata such as `unique_id`, `device_info`, entity category, capabilities, translation metadata, and ownership details

Without that, a remote integration can imitate state, but not actually behave like a real Home Assistant integration.

### 2. Device registry create and lookup APIs

The current public device registry websocket API is missing the operations needed for remote `device_info` support.

Missing:

- get a single device by id
- create a device
- get-or-create semantics
- a full subscription API with enough data to maintain a local mirror efficiently

Without these APIs, a remote integration host cannot correctly model device ownership.

### 3. Entity registry create/register API

The entity registry websocket API supports reading, updating, and removing entries, but not creating them.

Missing:

- create/register entity registry entry

This prevents a remote integration host from creating entity registry entries through the public API.

## Sync And Delta Gaps

### 4. Full-entry events for registries

Area, floor, label, and category registries mostly expose CRUD APIs already. The remaining problem is efficient synchronization.

Current registry events generally provide only:

- action
- id

They usually do not include the full updated entry payload. For a remote mirror, this means:

- every change may require re-fetching the whole registry
- there is no efficient incremental sync path

The ideal fix is either:

- full-entry payloads on create and update events, or
- a `get_single` API for each registry

### 5. Better device registry delta events

Device registry events do not provide enough payload on create and update to keep a local mirror current without re-listing everything.

The ideal fix is:

- full device payload on create
- full device payload on update
- optionally a dedicated `config/device_registry/get`

### 6. Service registry delta API with descriptions

Home Assistant exposes a full service snapshot, but register/remove events only identify the domain and service name.

Missing:

- service delta events that include the full service description and field schema

Without that, a remote mirror has to re-fetch the full service map whenever services are added or removed.

## Already Present In Home Assistant

These are not missing in Home Assistant core. They are available already and only need to be consumed by `hass-client`.

### Config entries

Config entries already have a usable remote API surface for listing, fetching, and subscribing.

### Area, floor, label, and category CRUD

These registries already expose CRUD operations. The missing part is efficient synchronization, not basic access.

## Suggested HA-Core Wishlist

If we want to propose concrete Home Assistant additions, the highest value items are:

1. A remote entity platform API for create, update, and remove with full integration metadata.
2. Device registry `get`, `create`, and `get_or_create` APIs.
3. Entity registry create/register API.
4. Full-entry delta subscriptions, or `get_single`, for area, floor, label, and category registries.
5. Service registry delta events with full service descriptions.

## Why This Matters

`hass-client` can already get close by mirroring states, services, and parts of the registries. The remaining gap is not simple data access. The real missing piece is the ability for an external process to participate in Home Assistant with the same ownership and lifecycle semantics as an in-process integration.
