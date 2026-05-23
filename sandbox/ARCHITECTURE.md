# Sandbox Entity Architecture

## Principles

1. **Integrations are unaware of sandboxing.** An integration running in a sandbox behaves identically to one running in the main process. It calls `async_add_entities`, registers services, writes state — the sandbox runtime handles the rest.
2. **EntityPlatform and EntityComponent are sandbox-aware.** The platform/component layer knows that some entities live remotely and manages proxy entities on the host side.
3. **The host HA instance is the source of truth** for entity registry, device registry, area assignments, and service routing.

## High-Level Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        Host HA Instance                          │
│                                                                  │
│  Config Entries:                                                 │
│    entry_1: domain=hue, sandbox=A                                │
│    entry_2: domain=esphome, sandbox=A                            │
│    entry_3: domain=zwave, sandbox=B                              │
│                                                                  │
│  Sandbox Integration:                                            │
│    Sandbox A → [entry_1, entry_2] → process + token              │
│    Sandbox B → [entry_3]          → process + token              │
│                                                                  │
│  EntityComponents (light, switch, sensor, ...):                  │
│    light:                                                        │
│      RemoteHostEntityPlatform(sandbox_A) → [RemoteLight, ...]    │
│      RemoteHostEntityPlatform(sandbox_B) → [RemoteLight, ...]    │
│      native platforms (if any)                                   │
│                                                                  │
└──────────────┬─────────────────────────────────┬─────────────────┘
               │ websocket (token A)             │ websocket (token B)
               ▼                                 ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│      Sandbox A           │    │         Sandbox B                │
│                          │    │                                  │
│  hass.sandbox → ws conn  │    │  hass.sandbox → ws conn          │
│                          │    │                                  │
│  Hue integration:        │    │  Z-Wave integration:             │
│    EntityPlatform(light)  │    │    EntityPlatform(switch)        │
│    → async_add_entities  │    │    → async_add_entities          │
│    → RemoteClient...     │    │    → RemoteClient...             │
│      registers on host   │    │      registers on host           │
└──────────────────────────┘    └──────────────────────────────────┘
```

## Startup Sequence

### 1. Host HA startup

During config entry loading, the host checks each entry for a sandbox marker:

```
config_entry.options["sandbox"] = "sandbox_id"
```

Any entry marked with a sandbox ID is **not** set up normally. Instead:

1. The sandbox integration is loaded (if not already).
2. The sandbox integration collects all entries grouped by sandbox ID.
3. For each sandbox ID, it:
   - Creates a system user and authorization token scoped to that sandbox.
   - Starts a sandbox subprocess, passing the token and host websocket URL.
   - Tracks which config entry IDs belong to which sandbox connection.

### 2. Sandbox process startup

The sandbox process:

1. Connects to the host via websocket using the sandbox token.
2. Reads core config (timezone, units, location) and applies it to the local `hass` object (`dt_util`, `hass.config`).
3. Fetches its assigned config entries via `sandbox/get_entries`.
4. Sets up each config entry using `async_setup_entry` — the integration runs normally.

### 3. Entity platform setup (sandbox side)

When an integration calls `async_add_entities(entities)` inside a sandbox, the platform is a **`RemoteClientEntityPlatform`**. Instead of registering entities locally only, it:

1. For each entity, sends a registration to the host:
   - `unique_id`, `entity_id` suggestion, `device_info`
   - Platform capabilities: `supported_features`, `supported_color_modes`, `device_class`, etc.
   - Entity category, icon, name
2. Receives back from the host:
   - Confirmed `entity_id` (host owns the entity registry)
   - `device_id` (host owns the device registry)
3. Sets up state forwarding: whenever `async_write_ha_state()` is called on the entity, the state + attributes are pushed to the host.

### 4. Entity platform setup (host side)

When the sandbox integration receives entity registrations, it:

1. Creates/updates device registry entries on the host.
2. Creates/updates entity registry entries on the host.
3. For each entity domain (light, switch, sensor, ...) that has entities from this sandbox:
   - Ensures a `RemoteHostEntityPlatform` is registered with the domain's `EntityComponent`.
   - Adds a `RemoteEntity` subclass (e.g., `RemoteLightEntity`) to that platform via `async_add_entities`.
4. The `RemoteEntity` proxy:
   - Holds cached state and attributes received from the sandbox.
   - Forwards service calls (turn_on, turn_off, etc.) to the sandbox via websocket.
   - Reports availability based on sandbox connection status.

## Entity Proxy Design

### RemoteLightEntity (host side, example)

```python
class RemoteLightEntity(LightEntity):
    """Proxy for a light entity living in a sandbox."""

    def __init__(self, sandbox_connection, registration_data):
        self._sandbox = sandbox_connection
        self._attr_unique_id = registration_data["unique_id"]
        self._attr_supported_color_modes = registration_data["supported_color_modes"]
        self._attr_supported_features = registration_data["supported_features"]
        # ... all static capabilities from registration

    @property
    def available(self) -> bool:
        return self._sandbox.connected and self._remote_available

    @property
    def is_on(self) -> bool:
        return self._state_cache["is_on"]

    @property
    def brightness(self) -> int | None:
        return self._state_cache.get("brightness")

    async def async_turn_on(self, **kwargs) -> None:
        await self._sandbox.forward_service_call(
            self.entity_id, "turn_on", kwargs
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self._sandbox.forward_service_call(
            self.entity_id, "turn_off", kwargs
        )
```

### Property caching

Service handlers on the host read entity properties synchronously during async service execution (e.g., `light` reads `supported_color_modes` to filter parameters before calling `async_turn_on`). The proxy must keep these cached and updated:

- **Static properties** (set at registration, rarely change): `supported_features`, `supported_color_modes`, `min_color_temp_kelvin`, `max_color_temp_kelvin`, `device_class`, `entity_category`
- **Dynamic properties** (change with state): `is_on`, `brightness`, `hs_color`, `color_temp_kelvin`, `effect`, `effect_list`, etc.

State updates from the sandbox push both the entity state and all relevant attributes to the host proxy.

### Service call forwarding

When the host calls `light.turn_on(area: living_room)`:

1. Host `light` EntityComponent resolves area → entity IDs (includes proxies).
2. Filters by `supported_features`, `device_class`, `available`.
3. Calls `entity.async_turn_on(**filtered_kwargs)` on each matched entity.
4. For `RemoteLightEntity`, this sends a websocket command to the sandbox.
5. Sandbox dispatches to the real entity's `async_turn_on`.
6. Entity updates state → pushed back to host proxy.

## State Synchronization

### Sandbox → Host (state push)

When a sandbox entity calls `self.async_write_ha_state()`:

```
Sandbox entity → RemoteClientEntityPlatform intercepts →
  websocket: sandbox/update_state {entity_id, state, attributes} →
    Host sandbox integration → RemoteEntity proxy updates cache →
      proxy.async_write_ha_state() on host
```

### Host → Sandbox (service calls)

```
User calls light.turn_on(area: living_room) on host →
  EntityComponent resolves targets → includes RemoteLightEntity →
    RemoteLightEntity.async_turn_on(**kwargs) →
      websocket: sandbox/call_service {entity_id, service, data} →
        Sandbox dispatches to real entity.async_turn_on(**kwargs)
```

## Device and Entity Registry

The **host** owns both registries:

- **Device registry**: The sandbox sends `DeviceInfo` from integrations. The host creates/updates device entries. Device IDs are host-assigned.
- **Entity registry**: The sandbox sends `unique_id` + `entity_id` suggestion. The host assigns the final `entity_id` (respecting user customizations). The sandbox must use the host-assigned entity_id.
- **Area assignment**: Done on the host. The sandbox doesn't know or care about areas.

## Sandbox Connection Lifecycle

1. **Connect**: Sandbox starts, connects, registers entities → host creates proxies.
2. **Running**: State flows bidirectionally. Service calls forwarded.
3. **Disconnect**: Host marks all proxy entities as `unavailable`. Entities remain in registries.
4. **Reconnect**: Sandbox re-registers entities. Host updates existing proxies, marks available.
5. **Removal**: Config entries removed from sandbox → host removes proxy entities and platforms.

## Data-Returning Entity Methods

Some entity methods return data (not just triggering actions). These work fine with async forwarding over websocket — the proxy method awaits a round-trip to get the data from the sandbox entity. This adds latency but is functionally correct.

| Domain | Method | Returns |
|---|---|---|
| `tts` | `async_get_tts_audio()` | `(extension, bytes)` |
| `stt` | `async_process_audio_stream()` | `SpeechResult` |
| `camera` | `async_camera_image()` | `bytes` |
| `camera` | `stream_source()` | `str` (URL) |
| `media_player` | `async_browse_media()` | `BrowseMedia` |
| `calendar` | `async_get_events()` | `list[CalendarEvent]` |
| `weather` | `async_get_forecasts()` | `list[Forecast]` |
| `conversation` | `async_process()` | `ConversationResult` |
| `image` | `async_image()` | `bytes` |
| `todo` | `async_get_items()` | `list[TodoItem]` |

The proxy entity implements the same async method, forwards the call via websocket to the sandbox, and returns the response. Same mechanism as service call forwarding — it's just a method call internally.

**Streaming edge cases** that need separate consideration:
- `camera.async_create_stream()` — creates a persistent Stream object for HLS/WebRTC
- `stt` with streaming audio input — continuous audio data flow
- `camera` WebRTC signaling — SDP offer/answer exchange

These may need a dedicated data channel or streaming websocket protocol.

## Entity Method Compatibility

Most entity domains already have `async_*` versions of all service-callable methods. Service handlers call the async wrappers, which is exactly what remote proxies need. The remote proxy just implements the `async_*` methods — no sync-to-async conversion needed.

**Already fully async** (no changes needed for proxy): light, switch, select, media_player, vacuum, camera, tts, stt, todo, number, button (async_press)

**Have sync + async wrapper pattern** (proxy implements async, works fine): climate, cover, fan, lock, alarm_control_panel, valve, water_heater, humidifier, siren, lawn_mower, remote

**Minor issues**:
- `cover.toggle` and `cover.toggle_tilt` — called directly without async wrappers in some code paths. Needs async versions added.

## Platform Granularity

Each config entry gets its own `EntityPlatform` per domain today (e.g., light + Hue config entry X = 1 platform). The sandbox follows the same model:

- Each sandboxed config entry that produces light entities → one `RemoteHostEntityPlatform` for light.
- The `RemoteHostEntityPlatform` creates `RemoteLight` entities and passes them to a real `EntityPlatform` via `async_add_entities`, so all normal EntityPlatform machinery (polling, state writes, registry) continues to work.
- Unloading a config entry removes its `RemoteHostEntityPlatform` and all its entities.

## Event Forwarding

Integrations fire events on the bus (e.g., `hue_event` for button presses, `zwave_js_value_notification`). The sandbox uses the existing websocket `fire_event` API to forward these to the host. No special mechanism needed — events are just JSON payloads on the bus.

## Config Flows

Config flows can be routed through the sandbox — the sandbox process runs the flow and reports results back to the host. This works for network-based integrations.

**To figure out later**: Config flows that access local hardware (serial ports, USB devices, Bluetooth) need the flow to run on the host where the hardware is, or need hardware forwarding into the sandbox.

## Open Questions

1. **Entity feature/capability updates**: If an integration dynamically changes `supported_features` (e.g., after firmware update), how is this communicated to the host proxy? Treat as part of state update, or separate capability-update message?

2. **Optimistic state updates**: Should `RemoteEntity.async_turn_on()` optimistically update the proxy state before the sandbox confirms, or wait for the state push? Optimistic reduces perceived latency but can cause brief inconsistencies.

3. **Entity removal during sandbox runtime**: If an integration removes an entity (e.g., device disconnected from Hue bridge), how does the sandbox signal the host to remove the proxy? Separate `sandbox/remove_entity` command?

4. **Diagnostics and debug**: How does `diagnostics` work for sandboxed integrations? The host has the config entry but the integration state lives in the sandbox.

5. **Camera streaming**: What's the data channel for HLS/WebRTC streams from sandbox camera entities? Websocket is too slow for video. Options: direct TCP forwarding, proxy URL that bridges to the sandbox, or sandbox exposes stream URL that host proxies.

6. **Sandbox process crash recovery**: If a sandbox process crashes, the host marks entities unavailable. On restart, does the sandbox re-register all entities, or does the host remember the previous registration and just wait for reconnection?
