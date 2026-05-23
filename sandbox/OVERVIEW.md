# Home Assistant Sandbox Architecture

## Goal

Run built-in Home Assistant integrations in an isolated sandbox process that connects back to a real Home Assistant instance. Entities created in the sandbox appear in the real HA, and service calls are forwarded transparently.

## High-Level Flow

```
┌─────────────────────────────────────────┐
│           Home Assistant Core           │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     sandbox integration         │    │
│  │                                 │    │
│  │  • finds config entries marked  │    │
│  │    for sandbox execution        │    │
│  │  • creates auth tokens per      │    │
│  │    sandbox instance             │    │
│  │  • spawns sandbox processes     │    │
│  │  • exposes websocket API:       │    │
│  │    sandbox/get_entries           │    │
│  │    sandbox/register_device      │    │
│  │    sandbox/register_entity      │    │
│  │    sandbox/update_state         │    │
│  └──────────┬──────────────────────┘    │
│             │ websocket (sandbox token)  │
└─────────────┼───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         Sandbox Process                 │
│         (hass-client)                   │
│                                         │
│  RemoteHomeAssistant subclass that:     │
│  1. Connects to HA Core with sandbox    │
│     token                               │
│  2. Calls sandbox/get_entries to learn  │
│     which config entries to represent   │
│  3. Sets up the integration locally     │
│  4. Registers entities/devices back to  │
│     HA Core via sandbox API             │
│  5. Pushes state updates to HA Core     │
└─────────────────────────────────────────┘
```

## Startup Sequence

### 1. Host HA startup

During config entry loading, the host checks each entry for a sandbox marker:

```
config_entry.options["sandbox"] = "<sandbox_id>"
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

When an integration calls `async_add_entities(entities)` inside a sandbox, the platform is a `RemoteClientEntityPlatform`. Instead of registering entities locally only, it:

1. For each entity, sends a registration to the host: `unique_id`, `entity_id` suggestion, `device_info`, platform capabilities (`supported_features`, `supported_color_modes`, `device_class`, …), entity category, icon, name.
2. Receives back from the host the confirmed host-assigned `entity_id` and `device_id`. (The host owns both registries; the sandbox must use the host's IDs.)
3. Sets up state forwarding so every `async_write_ha_state()` pushes state + attributes to the host.

### 4. Entity platform setup (host side)

When the sandbox integration receives entity registrations on the host, it:

1. Creates/updates device registry entries.
2. Creates/updates entity registry entries.
3. For each domain that has entities from this sandbox, ensures a `RemoteHostEntityPlatform` is registered with the domain's `EntityComponent` and adds the appropriate `RemoteEntity` subclass (e.g., `RemoteLightEntity`) via `async_add_entities`.
4. The proxy entity holds cached state and attributes, forwards service calls back to the sandbox via websocket, and reports availability based on sandbox connection status.

## Components

### 1. Sandbox Integration (HA Core side)

Lives at `core/homeassistant/components/sandbox/`.

**Config entries**: Config entries whose `options` contain `"sandbox": "<group_name>"` (a string value) are collected into sandbox groups. Entries sharing the same string run in the same sandbox process. On startup, the sandbox integration:

1. Queries all config entries where `options.sandbox` matches the group name (or uses the explicit entries list from `entry.data["entries"]` for testing).
2. For each sandbox group, creates a system user + refresh token.
3. Spawns a subprocess running the sandbox client, passing the access token.

**Websocket API** (guarded by sandbox tokens — only connections authenticated with a sandbox token can call these):

| Command | Description |
|---|---|
| `sandbox/get_entries` | Returns the config entry data assigned to this sandbox token |
| `sandbox/register_device` | Creates a device registry entry in HA Core |
| `sandbox/register_entity` | Creates an entity registry entry in HA Core |
| `sandbox/update_state` | Sets entity state in HA Core (like `hass.states.async_set`) |
| `sandbox/fire_event` | Fires an event on the HA Core bus |

Each command validates `connection.refresh_token_id` against the set of registered sandbox tokens before processing.

### 2. Sandbox Client (hass-client side)

Lives at `hass-client/hass_client/sandbox.py` with CLI at `hass-client/sandbox_runner.py`.

Extends `RemoteHomeAssistant` with sandbox-specific behavior:

1. **Bootstrap**: Connects to HA Core websocket using the sandbox token.
2. **Config fetch**: Calls `sandbox/get_entries` to get assigned config entries.
3. **Integration setup**: For each config entry, loads the integration's `async_setup_entry` (or `async_setup` for collection-based integrations like input helpers) and runs it.
4. **Entity bridge**: When local entities write state, intercepts and pushes to HA Core via `sandbox/update_state`. Registers entities/devices via the sandbox API.

### 3. Token System

For now, tokens are created dynamically at startup:

1. Sandbox integration creates a system user: `await hass.auth.async_create_system_user("Sandbox <entry_id>")`
2. Creates a refresh token: `await hass.auth.async_create_refresh_token(user)`
3. Creates an access token: `hass.auth.async_create_access_token(refresh_token)`
4. Stores mapping: `refresh_token.id → [config_entry_ids]`
5. Passes access token to the spawned sandbox process.

## Service Call Flow

`RemoteHomeAssistant` uses `HybridServiceRegistry` which provides local-first service resolution with remote fallback:

1. Service call arrives (e.g., `input_boolean.turn_on`)
2. Try local registry first (integration loaded in sandbox)
3. If `ServiceNotFound` locally, check if the service exists in the remote cache
4. If it exists remotely, forward via websocket to HA Core
5. Fire `EVENT_CALL_SERVICE` locally for event listeners

This allows sandbox integrations to call services on other integrations running in HA Core, while keeping local services fast.

## Test Infrastructure

Two pytest plugins validate compatibility by running HA Core's own test suites:

### Base Plugin (`hass_client.testing.pytest_plugin`)

Replaces `HomeAssistant` with `RemoteHomeAssistant` as a drop-in. No real websocket — validates the client library's API compatibility.

### Sandbox Plugin (`hass_client.testing.conftest_sandbox`)

Full end-to-end: boots a host HA Core with websocket_api + sandbox, starts a real aiohttp test server, creates a sandbox auth token, and connects the sandbox RemoteHomeAssistant via live websocket. Each test gets a fresh host + sandbox pair.

Key mechanisms:
- **Socket bypass**: Saves real socket before pytest-socket blocks it, restores during sandbox setup
- **Freezer detection**: Falls back to base plugin for tests using `freezer.move_to()` (time jumps hang live connections)
- **Dual-instance lifecycle**: Host HA is explicitly stopped in teardown to cancel its timers

### Compatibility Status

33 integrations tested through real sandbox websocket: 878/880 tests pass (99.8%). Includes input helpers, automation, script, scene, todo, group, recorder, and many sensor/helper platforms. See `hass-client/SANDBOX_COMPAT.md` for the full report.

## Entity Platform Architecture

### Host side: RemoteHostEntityPlatform

When a sandbox registers entities via `sandbox/register_entity`, the host creates a `RemoteHostEntityPlatform` instance (if one doesn't exist for that domain) and adds it directly to the domain's `EntityComponent._platforms`. This platform manages **proxy entities** — real HA entity instances that:

- Live in the host's entity/device/area registries (enabling targeting)
- Cache state pushed from the sandbox via `sandbox/update_state`
- Forward service calls (turn_on, activate, etc.) back to the sandbox via a websocket subscription

The proxy entity classes live in `entity/` (one file per platform, 32 supported domains). `RemoteHostEntityPlatform` replaces the previous approach of 32 identical per-domain platform setup files.

A typical proxy looks like:

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

Service handlers read entity properties synchronously during async service execution (e.g., `light` reads `supported_color_modes` to filter parameters before calling `async_turn_on`), so the proxy keeps both **static** properties (set at registration: `supported_features`, `supported_color_modes`, color-temp range, `device_class`, `entity_category`) and **dynamic** properties (`is_on`, `brightness`, `hs_color`, `color_temp_kelvin`, `effect`, …) cached locally. State updates from the sandbox push both the entity state and all relevant attributes.

### Sandbox side: RemoteClientEntityPlatform

On the sandbox side, `RemoteClientEntityPlatform` wraps the integration's `EntityPlatform` to intercept `async_add_entities`. When an integration adds entities:

1. Entities are added locally as normal (so they work in the sandbox)
2. Each entity is registered with the host via `sandbox/register_entity`
3. State changes are forwarded to the host via `sandbox/update_state`
4. Method calls from the host are dispatched to local entities

### Supported platforms (32)

`alarm_control_panel`, `binary_sensor`, `button`, `calendar`, `climate`, `cover`, `date`, `datetime`, `device_tracker`, `event`, `fan`, `humidifier`, `lawn_mower`, `light`, `lock`, `media_player`, `notify`, `number`, `remote`, `scene`, `select`, `sensor`, `siren`, `switch`, `text`, `time`, `todo`, `update`, `vacuum`, `valve`, `water_heater`, `weather`

### Service call flow

1. User calls `light.turn_on` targeting a sandbox proxy entity
2. HA's service handler invokes `async_turn_on` on the proxy
3. Proxy sends command via `send_command` → websocket subscription event
4. Sandbox receives the event, executes the method on the real entity
5. Sandbox sends `sandbox/entity_command_result` back
6. Proxy's future resolves, service call completes

## Entity Method Compatibility

Most entity domains already expose `async_*` versions of every service-callable method. Service handlers call those async wrappers, which is exactly what the remote proxies need — the proxy implements the `async_*` methods and forwards the call. No sync-to-async conversion required.

- **Already fully async** (no changes needed for proxy): `light`, `switch`, `select`, `media_player`, `vacuum`, `camera`, `tts`, `stt`, `todo`, `number`, `button` (`async_press`).
- **Sync + async-wrapper pattern** (proxy implements async, works as-is): `climate`, `cover`, `fan`, `lock`, `alarm_control_panel`, `valve`, `water_heater`, `humidifier`, `siren`, `lawn_mower`, `remote`.
- **Minor issues**: `cover.toggle` and `cover.toggle_tilt` are called directly without async wrappers in some code paths; they need async versions added.

## Known Limitations / Future Work

- **YAML-only integrations**: Not supported in sandbox. We are only interested in config-entry-based integrations. YAML integrations that don't use config entries are out of scope.
- **Shutdown / graceful teardown**: When HA Core is shutting down, it should send a shutdown command to each sandbox process. The sandbox should collect restore-state data from its entities and push it back to the host before exiting. The host owns the restore state storage. Not yet implemented.
- **Store persistence**: Integrations use `Store` objects for persistent data (e.g., token caches, device databases). These stores should be routed through the sandbox websocket so the host owns and persists them. The sandbox should call a `sandbox/store_save` command when writing, and `sandbox/store_load` on startup. This keeps all persistent state on the host filesystem. Not yet implemented.
- **Custom integrations**: Future goal. Current focus is built-in integrations only.
- **Logbook platform discovery**: The logbook integration's platform loading doesn't find automation/script logbook callbacks in the sandbox environment. Low priority — cosmetic only.
