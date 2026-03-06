# ESPHome Dashboard Version Reporting Fix

## Problem Statement

The `esphome_dashboard` integration reports incorrect device versions. It currently uses the `deployed_version` field from the ESPHome Dashboard API, which can be stale or inaccurate.

The correct approach (as implemented in the `esphome` integration's `ESPHomeDashboardUpdateEntity`) is:
- **Installed version**: Query the actual device for its `esphome_version`
- **Latest version**: Use `current_version` from the dashboard (the target version available in YAML config)

## Solution Overview

Implement a three-tier version source hierarchy:

1. **ESPHome Integration** (preferred): If the device is also configured in the `esphome` integration, use `RuntimeEntryData.device_info.esphome_version`
2. **Direct Native API**: Query the device directly using `aioesphomeapi` library
3. **Dashboard Fallback**: Use `deployed_version` from the dashboard API

## Architecture

### Data Flow

```
Entity Created
    │
    ▼
Check esphome integration for device
    │
    ├─(found)──────────────────┐
    │                          ▼
    │                   Use esphome_version
    │                          │
    │                          ▼
    │                   Subscribe to updates
    │
    └─(not found)──────────────┐
                               ▼
                    Discover port via mDNS
                               │
                               ▼
                    Query via native API
                               │
               ┌───────────────┴───────────────┐
               │                               │
          (success)                       (failure)
               │                               │
               ▼                               ▼
        Cache version              Use deployed_version
```

### Version Property Logic

```python
@property
def installed_version(self) -> str | None:
    """Return installed version with priority: esphome > cached > dashboard."""
    # Priority 1: ESPHome integration (authoritative, live updates)
    if self._esphome_entry_data and self._esphome_entry_data.device_info:
        return self._esphome_entry_data.device_info.esphome_version

    # Priority 2: Cached version from direct API query
    if self._cached_device_version:
        return self._cached_device_version

    # Priority 3: Fallback to dashboard's deployed_version
    return self.coordinator.data[self._device_name].get("deployed_version")
```

## Implementation Details

### 1. ESPHome Integration Lookup

Find the `RuntimeEntryData` for a device by name:

```python
from homeassistant.config_entries import ConfigEntryState

def _find_esphome_entry_data(
    hass: HomeAssistant, device_name: str
) -> RuntimeEntryData | None:
    """Find RuntimeEntryData for an ESPHome device by name."""
    for entry in hass.config_entries.async_entries("esphome"):
        if entry.state != ConfigEntryState.LOADED:
            continue
        entry_data: RuntimeEntryData = entry.runtime_data
        if entry_data.device_info and entry_data.device_info.name == device_name:
            return entry_data
    return None
```

When found, subscribe to device updates:

```python
self.async_on_remove(
    entry_data.async_subscribe_device_updated(
        self._handle_esphome_device_update
    )
)
```

### 2. Port Discovery via mDNS

ESPHome devices advertise their native API port via mDNS service `_esphomelib._tcp.local.`:

```python
from zeroconf.asyncio import AsyncServiceInfo

ESPHOME_SERVICE_TYPE = "_esphomelib._tcp.local."

async def _async_discover_device_port(self, device_name: str) -> int | None:
    """Discover device port via mDNS."""
    from homeassistant.components import zeroconf

    aiozc = await zeroconf.async_get_async_instance(self.hass)
    service_name = f"{device_name}.{ESPHOME_SERVICE_TYPE}"

    info = AsyncServiceInfo(ESPHOME_SERVICE_TYPE, service_name)
    if await info.async_request(aiozc.zeroconf, timeout=3.0):
        return info.port
    return None
```

### 3. Direct Native API Query

Query the device directly when not in the esphome integration:

```python
from aioesphomeapi import APIClient, APIConnectionError
from homeassistant.components.esphome.const import DEFAULT_PORT

async def _async_query_device_version(self, address: str) -> str | None:
    """Query device version directly via native API."""
    # Discover port via mDNS, fall back to default
    port = await self._async_discover_device_port(self._device_name)
    if port is None:
        port = DEFAULT_PORT

    client = APIClient(address, port=port, password="")
    try:
        await client.connect(login=False)
        device_info = await client.device_info()
        return device_info.esphome_version
    except APIConnectionError:
        # Device offline, encrypted, or unreachable
        return None
    finally:
        await client.disconnect()
```

### 4. Entity Initialization

```python
def __init__(self, coordinator, device_name, device_data, mac_address):
    # ... existing init code ...

    # Version tracking
    self._esphome_entry_data: RuntimeEntryData | None = None
    self._cached_device_version: str | None = None
    self._version_query_done: bool = False

async def async_added_to_hass(self) -> None:
    """Handle entity added to Home Assistant."""
    await super().async_added_to_hass()

    # Try to find esphome integration entry for this device
    self._esphome_entry_data = _find_esphome_entry_data(
        self.hass, self._device_name
    )

    if self._esphome_entry_data:
        # Subscribe to device updates for version changes
        self.async_on_remove(
            self._esphome_entry_data.async_subscribe_device_updated(
                self._handle_esphome_device_update
            )
        )
    else:
        # Query device directly (runs in background)
        self.hass.async_create_task(self._async_fetch_device_version())
```

### 5. Caching Strategy

- Cache direct API query results in `self._cached_device_version`
- Cache persists until OTA update is performed
- Clear cache when OTA starts to force re-query
- For esphome integration devices: no caching needed (live updates via subscription)

### 6. Post-OTA Update Flow

```python
async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
    """Install an update."""
    # ... existing compile and upload logic ...

    # Clear cached version to force re-query after OTA
    self._cached_device_version = None
    self._version_query_done = False

    # Refresh coordinator data from dashboard
    await self.coordinator.async_request_refresh()

    # If not using esphome integration, re-query device version
    if not self._esphome_entry_data:
        # Schedule delayed version query (device reboots after OTA)
        self.hass.async_create_task(
            self._async_delayed_version_query(delay=30)
        )

async def _async_delayed_version_query(self, delay: float) -> None:
    """Query device version after a delay (for post-OTA reboot)."""
    await asyncio.sleep(delay)
    await self._async_fetch_device_version()
    self.async_write_ha_state()
```

### 7. Dynamic ESPHome Integration Discovery

Handle case where esphome integration loads after esphome_dashboard:

```python
@callback
def _handle_coordinator_update(self) -> None:
    """Handle updated data from the coordinator."""
    # Re-check for esphome integration if not already linked
    if not self._esphome_entry_data:
        entry_data = _find_esphome_entry_data(self.hass, self._device_name)
        if entry_data:
            self._esphome_entry_data = entry_data
            self.async_on_remove(
                entry_data.async_subscribe_device_updated(
                    self._handle_esphome_device_update
                )
            )
            # Clear cached version since esphome has authoritative data
            self._cached_device_version = None

    # ... rest of coordinator update handling ...
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Device not in esphome integration | Try direct API query |
| mDNS port discovery fails | Fall back to DEFAULT_PORT (6053) |
| Direct API query fails (offline) | Use cached version if available, else dashboard's `deployed_version` |
| Direct API query fails (encrypted) | Use dashboard's `deployed_version` |
| ESPHome integration loads later | Re-check on coordinator updates, switch to esphome source |

## Logging

- Debug: "Using version from esphome integration for {device}"
- Debug: "Querying {device} directly for version via port {port}"
- Debug: "Direct query failed for {device}, using dashboard version"
- Debug: "Discovered port {port} for {device} via mDNS"

## Files to Modify

1. **`homeassistant/components/esphome_dashboard/update.py`**
   - Add `_find_esphome_entry_data()` helper function
   - Add `_async_discover_device_port()` method
   - Add `_async_query_device_version()` method
   - Add `_async_fetch_device_version()` method
   - Add `_async_delayed_version_query()` method
   - Add `_handle_esphome_device_update()` callback
   - Modify `__init__()` to add version tracking attributes
   - Add `async_added_to_hass()` method
   - Modify `_handle_coordinator_update()` for dynamic esphome discovery
   - Add `installed_version` property
   - Modify `async_install()` to clear cache and trigger re-query

2. **`homeassistant/components/esphome_dashboard/manifest.json`**
   - Verify `aioesphomeapi` is available (inherited from esphome dependency)
   - Add `after_dependencies: ["esphome", "zeroconf"]` if not present

3. **`tests/components/esphome_dashboard/test_update.py`**
   - Add tests for esphome integration lookup
   - Add tests for direct API query
   - Add tests for fallback behavior
   - Add tests for post-OTA version refresh
   - Add tests for dynamic esphome discovery

## Testing Strategy

1. **Unit Tests:**
   - Mock esphome integration entries
   - Mock direct API responses
   - Mock mDNS discovery
   - Test version priority logic
   - Test error handling paths

2. **Integration Tests:**
   - Test with real esphome integration loaded
   - Test coordinator update triggers
   - Test OTA flow with version refresh

## Dependencies

- `aioesphomeapi` - For direct device queries (already a requirement of esphome)
- `zeroconf` - For port discovery via mDNS (core Home Assistant component)
- `homeassistant.components.esphome` - For RuntimeEntryData access (soft dependency)
