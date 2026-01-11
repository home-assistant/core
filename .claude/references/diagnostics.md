# Diagnostics Reference

## Overview

Diagnostics provide a way to collect and export integration data for troubleshooting purposes. This is a **Gold tier** quality scale requirement that helps users and developers debug issues.

## When to Implement Diagnostics

Diagnostics are required for:
- ✅ Gold tier and above integrations
- ✅ Any integration where users might need support
- ✅ Integrations with complex configuration or state

## Diagnostics Types

Home Assistant supports two types of diagnostics:

### 1. Config Entry Diagnostics
Provides data about a specific configuration entry.

**File**: `diagnostics.py` in your integration folder

```python
"""Diagnostics support for My Integration."""
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

TO_REDACT = {
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "username",
    "email",
    "latitude",
    "longitude",
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator_data": coordinator.data.to_dict(),
        "last_update_success": coordinator.last_update_success,
        "last_update": coordinator.last_update_success_time.isoformat()
        if coordinator.last_update_success_time
        else None,
    }
```

### 2. Device Diagnostics
Provides data about a specific device.

```python
async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: dr.DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = entry.runtime_data

    # Find device identifier
    device_id = None
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            device_id = identifier[1]
            break

    if device_id is None:
        return {}

    device_data = coordinator.data.devices.get(device_id)
    if device_data is None:
        return {}

    return {
        "device_info": {
            "id": device_id,
            "name": device_data.name,
            "model": device_data.model,
            "firmware": device_data.firmware_version,
        },
        "device_data": device_data.to_dict(),
        "entities": [
            {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "state": hass.states.get(entity.entity_id).state
                if (state := hass.states.get(entity.entity_id))
                else None,
            }
            for entity in er.async_entries_for_device(
                er.async_get(hass), device.id, include_disabled_entities=True
            )
        ],
    }
```

## Data Redaction

**CRITICAL**: Always redact sensitive information!

### What to Redact

Always redact:
- API keys, tokens, secrets
- Passwords, credentials
- Email addresses, usernames
- Precise GPS coordinates (latitude, longitude)
- MAC addresses (sometimes)
- Serial numbers (if sensitive)
- Personal information

### Using async_redact_data

```python
from homeassistant.helpers import async_redact_data

# Basic redaction
data = async_redact_data(entry.data, TO_REDACT)

# With nested redaction
TO_REDACT = {
    "api_key",
    "auth.password",  # Nested key
    "user.email",     # Nested key
}

# Redacting from multiple sources
diagnostics = {
    "config": async_redact_data(entry.data, TO_REDACT),
    "options": async_redact_data(entry.options, TO_REDACT),
    "coordinator": async_redact_data(coordinator.data, TO_REDACT),
}
```

### Custom Redaction

For complex data structures:

```python
def redact_device_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive device data."""
    redacted = data.copy()

    # Redact specific fields
    if "serial_number" in redacted:
        redacted["serial_number"] = "**REDACTED**"

    # Redact nested structures
    if "location" in redacted:
        redacted["location"] = {
            "city": redacted["location"].get("city"),
            # Don't include exact coordinates
        }

    return redacted
```

## What to Include

### Good Diagnostic Data

Include information helpful for troubleshooting:
- ✅ Integration version/state
- ✅ Configuration (redacted)
- ✅ Coordinator/connection status
- ✅ Device information (model, firmware)
- ✅ API response examples (redacted)
- ✅ Error states
- ✅ Entity states
- ✅ Feature flags/capabilities

### Example Comprehensive Diagnostics

```python
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        # Integration state
        "integration": {
            "version": coordinator.version,
            "entry_id": entry.entry_id,
            "title": entry.title,
            "state": entry.state,
        },
        # Configuration (redacted)
        "configuration": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        # Connection/Coordinator status
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update": coordinator.last_update_success_time.isoformat()
            if coordinator.last_update_success_time
            else None,
            "update_interval": coordinator.update_interval.total_seconds(),
            "last_exception": str(coordinator.last_exception)
            if coordinator.last_exception
            else None,
        },
        # Device/System information
        "devices": {
            device_id: {
                "name": device.name,
                "model": device.model,
                "firmware": device.firmware,
                "features": device.supported_features,
                "state": device.state,
            }
            for device_id, device in coordinator.data.devices.items()
        },
        # API information (redacted)
        "api": {
            "endpoint": coordinator.client.endpoint,
            "authenticated": coordinator.client.is_authenticated,
            "rate_limit_remaining": coordinator.client.rate_limit_remaining,
        },
    }
```

## Testing Diagnostics

### Test File Structure

```python
"""Test diagnostics."""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.components.my_integration import setup_integration


async def test_entry_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    # Verify structure
    assert "entry" in diagnostics
    assert "coordinator_data" in diagnostics

    # Verify redaction
    assert "api_key" not in str(diagnostics)
    assert "password" not in str(diagnostics)

    # Verify useful data is present
    assert diagnostics["entry"]["title"] == "My Device"
    assert diagnostics["coordinator_data"]["devices"]


async def test_device_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device diagnostics."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "device_id")}
    )
    assert device

    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device
    )

    # Verify device-specific data
    assert diagnostics["device_info"]["id"] == "device_id"
    assert "entities" in diagnostics
```

## Common Patterns

### Pattern 1: Coordinator-Based Integration

```python
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "data": coordinator.data.to_dict(),
        }
    }
```

### Pattern 2: Multiple Coordinators

```python
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data

    return {
        "device_coordinator": data.device_coordinator.data.to_dict(),
        "status_coordinator": data.status_coordinator.data.to_dict(),
    }
```

### Pattern 3: Hub with Multiple Devices

```python
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = entry.runtime_data

    return {
        "hub": {
            "connected": hub.connected,
            "version": hub.version,
        },
        "devices": {
            device_id: device.to_dict()
            for device_id, device in hub.devices.items()
        },
    }
```

## Best Practices

### ✅ DO

- Redact all sensitive information
- Include coordinator state and update times
- Provide device/system information
- Include error messages (if present)
- Make data easily readable
- Test that redaction works
- Include API/connection status

### ❌ DON'T

- Include raw passwords, tokens, or API keys
- Include precise GPS coordinates
- Include personal information (emails, names)
- Make diagnostics too large (>1MB)
- Include binary data
- Assume all fields are present (use .get())
- Include sensitive serial numbers

## Troubleshooting

### Diagnostics Not Appearing

Check:
1. File named `diagnostics.py` in integration folder
2. Function named exactly `async_get_config_entry_diagnostics`
3. Proper import of `ConfigEntry` and `HomeAssistant`
4. Integration is loaded successfully

### Redaction Not Working

Check:
1. Using `async_redact_data` from `homeassistant.helpers`
2. Field names match exactly (case-sensitive)
3. Nested fields use dot notation: `"auth.password"`
4. TO_REDACT is a set, not a list

### Device Diagnostics Not Working

Check:
1. Device has proper identifiers
2. Function named exactly `async_get_device_diagnostics`
3. Device parameter is `dr.DeviceEntry`
4. Proper device lookup logic

## Quality Scale Considerations

Diagnostics are required for **Gold tier** integrations:
- Must implement config entry diagnostics
- Should implement device diagnostics (if applicable)
- Must redact all sensitive information
- Should provide comprehensive troubleshooting data

## References

- Quality Scale Rule: `diagnostics`
- Home Assistant Docs: [Integration Diagnostics](https://developers.home-assistant.io/docs/integration_fetching_data)
- Helper Functions: `homeassistant.helpers.redact`
