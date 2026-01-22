# Services Reference

Services allow automations and users to trigger actions.

## Service Registration

Register services in `async_setup`, NOT in `async_setup_entry`:

```python
"""My Integration setup."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN

SERVICE_REFRESH = "refresh"
SERVICE_SET_SCHEDULE = "set_schedule"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up My Integration services."""

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]

        if not (entry := hass.config_entries.async_get_entry(entry_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )

        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
            )

        coordinator = entry.runtime_data
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
        schema=vol.Schema({
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        }),
    )

    return True
```

## Service with Response

```python
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up services with response."""

    async def handle_get_schedule(call: ServiceCall) -> ServiceResponse:
        """Handle get_schedule service call."""
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]

        if not (entry := hass.config_entries.async_get_entry(entry_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )

        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
            )

        coordinator = entry.runtime_data
        schedule = await coordinator.client.get_schedule()

        return {
            "schedule": [
                {"day": item.day, "start": item.start, "end": item.end}
                for item in schedule
            ]
        }

    hass.services.async_register(
        DOMAIN,
        "get_schedule",
        handle_get_schedule,
        schema=vol.Schema({
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        }),
        supports_response=SupportsResponse.ONLY,  # or SupportsResponse.OPTIONAL
    )

    return True
```

## Entity Services

Register entity-specific services in platform setup:

```python
"""Switch platform with entity service."""

from homeassistant.helpers.entity_platform import AddEntitiesCallback
import voluptuous as vol


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from config entry."""
    coordinator = entry.runtime_data

    async_add_entities([PowerSwitch(coordinator)])

    # Register entity service
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_timer",
        {
            vol.Required("minutes"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=120)
            ),
        },
        "async_set_timer",
    )


class PowerSwitch(MyEntity, SwitchEntity):
    """Power switch with timer service."""

    async def async_set_timer(self, minutes: int) -> None:
        """Set auto-off timer."""
        await self.coordinator.client.set_timer(minutes)
```

## Service Validation

```python
from homeassistant.exceptions import ServiceValidationError


async def handle_set_schedule(call: ServiceCall) -> None:
    """Handle set_schedule service call."""
    start_date = call.data["start_date"]
    end_date = call.data["end_date"]

    # Validate input
    if end_date < start_date:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_date_before_start_date",
        )

    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = hass.config_entries.async_get_entry(entry_id)

    try:
        await entry.runtime_data.client.set_schedule(start_date, end_date)
    except MyConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
        ) from err
```

## services.yaml

Define services in `services.yaml`:

```yaml
refresh:
  name: Refresh
  description: Force a data refresh from the device.
  fields:
    config_entry_id:
      name: Config entry ID
      description: The config entry to refresh.
      required: true
      selector:
        config_entry:
          integration: my_integration

set_schedule:
  name: Set schedule
  description: Set the device schedule.
  fields:
    config_entry_id:
      name: Config entry ID
      description: The config entry to configure.
      required: true
      selector:
        config_entry:
          integration: my_integration
    start_date:
      name: Start date
      description: Schedule start date.
      required: true
      selector:
        date:
    end_date:
      name: End date
      description: Schedule end date.
      required: true
      selector:
        date:

get_schedule:
  name: Get schedule
  description: Get the current device schedule.
  fields:
    config_entry_id:
      name: Config entry ID
      description: The config entry to query.
      required: true
      selector:
        config_entry:
          integration: my_integration

set_timer:
  name: Set timer
  description: Set auto-off timer for the switch.
  target:
    entity:
      integration: my_integration
      domain: switch
  fields:
    minutes:
      name: Minutes
      description: Timer duration in minutes.
      required: true
      selector:
        number:
          min: 1
          max: 120
          unit_of_measurement: min
```

## Exception Translations

In `strings.json`:

```json
{
  "exceptions": {
    "entry_not_found": {
      "message": "Config entry not found."
    },
    "entry_not_loaded": {
      "message": "Config entry is not loaded."
    },
    "end_date_before_start_date": {
      "message": "The end date cannot be before the start date."
    },
    "connection_failed": {
      "message": "Failed to connect to the device."
    }
  }
}
```

## Device-Based Service Targeting

```python
async def handle_device_service(call: ServiceCall) -> None:
    """Handle service call targeting a device."""
    device_id = call.data[ATTR_DEVICE_ID]

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    # Find config entry for device
    entry_id = next(
        (entry_id for entry_id in device.config_entries if entry_id),
        None,
    )

    if entry_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
        )

    entry = hass.config_entries.async_get_entry(entry_id)
    # ... continue with service logic
```

## Service Schema Patterns

```python
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

# Basic schema
SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required("value"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional("timeout", default=30): cv.positive_int,
})

# With entity targeting
SERVICE_SCHEMA_ENTITY = vol.Schema({
    vol.Required("entity_id"): cv.entity_ids,
    vol.Required("parameter"): cv.string,
})

# With selectors (for services.yaml)
# Use selector in services.yaml, not in Python schema
```

## Quality Scale Requirements

- **Bronze**: `action-setup` - Register services in `async_setup` if integration has services
- Services must validate config entry state before use
- Use translated exceptions for error messages
