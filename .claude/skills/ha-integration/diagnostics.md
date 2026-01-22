# Diagnostics Reference

Diagnostics provide debug information for troubleshooting integrations.

## Basic Diagnostics

```python
"""Diagnostics support for My Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import MyIntegrationConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    CONF_PASSWORD,
    CONF_TOKEN,
    "serial_number",
    "mac_address",
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MyIntegrationConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "coordinator_data": async_redact_data(
            coordinator.data.to_dict(), TO_REDACT
        ),
    }
```

## What to Include

**Do include:**
- Configuration data (redacted)
- Current coordinator data
- Device information
- Error states and counts
- Connection status
- Firmware versions
- Feature flags

**Never include (always redact):**
- API keys, tokens, passwords
- Geographic coordinates (latitude/longitude)
- Personal identifiable information
- Email addresses
- MAC addresses (unless needed for debugging)
- Serial numbers (unless needed for debugging)

## Comprehensive Diagnostics

```python
"""Diagnostics support for My Integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MyIntegrationConfigEntry
from .const import DOMAIN

TO_REDACT = {
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    "serial",
    "serial_number",
    "mac",
    "mac_address",
    "email",
    "access_token",
    "refresh_token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MyIntegrationConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Get device registry entries
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    devices = []
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        entities = []
        for entity in er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        ):
            entities.append({
                "entity_id": entity.entity_id,
                "unique_id": entity.unique_id,
                "platform": entity.platform,
                "disabled": entity.disabled,
                "disabled_by": entity.disabled_by,
            })

        devices.append({
            "name": device.name,
            "model": device.model,
            "manufacturer": device.manufacturer,
            "sw_version": device.sw_version,
            "hw_version": device.hw_version,
            "identifiers": list(device.identifiers),
            "connections": list(device.connections),
            "entities": entities,
        })

    return {
        "entry": {
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "data": async_redact_data(coordinator.data.to_dict(), TO_REDACT),
        },
        "devices": devices,
    }
```

## Device-Level Diagnostics

For integrations with multiple devices, you can also provide device-level diagnostics:

```python
async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: MyIntegrationConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = entry.runtime_data

    # Find device data based on device identifiers
    device_id = next(
        (id for domain, id in device.identifiers if domain == DOMAIN), None
    )

    if device_id is None:
        return {"error": "Device not found"}

    device_data = coordinator.data.devices.get(device_id)
    if device_data is None:
        return {"error": "Device data not found"}

    return {
        "device_info": {
            "name": device.name,
            "model": device.model,
            "sw_version": device.sw_version,
        },
        "device_data": async_redact_data(device_data.to_dict(), TO_REDACT),
    }
```

## Redaction Patterns

### Simple Redaction

```python
from homeassistant.components.diagnostics import async_redact_data

data = {"api_key": "secret123", "temperature": 21.5}
redacted = async_redact_data(data, {"api_key"})
# Result: {"api_key": "**REDACTED**", "temperature": 21.5}
```

### Nested Redaction

`async_redact_data` handles nested dictionaries automatically:

```python
data = {
    "config": {
        "host": "192.168.1.1",
        "api_key": "secret123",
    },
    "device": {
        "name": "My Device",
        "serial_number": "ABC123",
    }
}
redacted = async_redact_data(data, {"api_key", "serial_number"})
# Result: {"config": {"host": "192.168.1.1", "api_key": "**REDACTED**"},
#          "device": {"name": "My Device", "serial_number": "**REDACTED**"}}
```

### Custom Redaction

For complex redaction needs:

```python
def _redact_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive data."""
    result = dict(data)

    # Redact specific keys
    for key in ("api_key", "token", "password"):
        if key in result:
            result[key] = "**REDACTED**"

    # Redact partial data (e.g., keep last 4 chars)
    if "serial" in result:
        result["serial"] = f"****{result['serial'][-4:]}"

    # Redact coordinates to city level
    if "latitude" in result:
        result["latitude"] = round(result["latitude"], 1)
    if "longitude" in result:
        result["longitude"] = round(result["longitude"], 1)

    return result
```

## Testing Diagnostics

```python
from homeassistant.components.diagnostics import REDACTED

from custom_components.my_integration.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    diagnostics = await async_get_config_entry_diagnostics(hass, init_integration)

    assert diagnostics["entry"]["data"]["host"] == "192.168.1.1"
    assert diagnostics["entry"]["data"]["api_key"] == REDACTED
    assert "temperature" in diagnostics["coordinator"]["data"]
```

## Quality Scale Requirement

Diagnostics are required for **Gold** quality scale and above. Ensure your `quality_scale.yaml` includes:

```yaml
rules:
  diagnostics: done
```
