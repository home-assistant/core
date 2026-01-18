# Service Actions

This skill covers registering and implementing service actions for Home Assistant integrations.

## When to Use

- Adding custom service actions to an integration
- Registering entity-specific services
- Implementing service validation and error handling

## Core Requirement

**Register all service actions in `async_setup`, NOT in `async_setup_entry`.**

This is a Bronze quality scale requirement (`action-setup`).

## Integration-Level Services

### Registration in __init__.py

```python
"""The My Integration integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

ATTR_CONFIG_ENTRY_ID = "config_entry_id"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up My Integration."""

    async def async_my_service(call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]

        # Validate config entry exists
        if not (entry := hass.config_entries.async_get_entry(entry_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )

        # Validate config entry is loaded
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
            )

        # Get client from runtime data
        client = entry.runtime_data.client

        # Perform the action
        try:
            result = await client.async_perform_action(call.data["parameter"])
        except MyConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err

        return {"result": result}

    hass.services.async_register(
        DOMAIN,
        "my_service",
        async_my_service,
        schema=vol.Schema({
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            vol.Required("parameter"): cv.string,
        }),
    )

    return True
```

## Entity Services

Register on platform setup:

```python
"""Sensor platform."""

from homeassistant.helpers.entity_platform import AddEntitiesCallback

async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "calibrate",
        {
            vol.Required("offset"): cv.positive_float,
        },
        "async_calibrate",
    )

    async_add_entities([MySensor(entry.runtime_data)])


class MySensor(SensorEntity):
    """Sensor with custom service."""

    async def async_calibrate(self, offset: float) -> None:
        """Calibrate the sensor."""
        await self.coordinator.client.async_calibrate(offset)
        await self.coordinator.async_request_refresh()
```

## Service Schema Validation

```python
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

SERVICE_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_ids,
    vol.Required("parameter"): cv.string,
    vol.Optional("timeout", default=30): cv.positive_int,
    vol.Optional("start_date"): cv.date,
    vol.Optional("end_date"): cv.date,
})
```

## Exception Handling

### Use Specific Exceptions

```python
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
)

# For invalid user input
if end_date < start_date:
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="end_date_before_start_date",
    )

# For device/service communication errors
try:
    await client.async_set_schedule(start_date, end_date)
except MyConnectionError as err:
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="connection_error",
    ) from err
```

### Exception Translations (Gold)

In `strings.json`:

```json
{
  "exceptions": {
    "entry_not_found": {
      "message": "Config entry not found"
    },
    "entry_not_loaded": {
      "message": "Config entry is not loaded"
    },
    "end_date_before_start_date": {
      "message": "End date must be after start date"
    },
    "connection_error": {
      "message": "Failed to connect to device"
    }
  }
}
```

## services.yaml

Create `services.yaml` with descriptions:

```yaml
my_service:
  name: My service
  description: Performs a custom action on the device.
  fields:
    config_entry_id:
      name: Config entry
      description: The config entry to use.
      required: true
      selector:
        config_entry:
          integration: my_integration
    parameter:
      name: Parameter
      description: The parameter value to set.
      required: true
      example: "value"
      selector:
        text:

calibrate:
  name: Calibrate
  description: Calibrate the sensor with an offset.
  target:
    entity:
      integration: my_integration
      domain: sensor
  fields:
    offset:
      name: Offset
      description: The calibration offset.
      required: true
      selector:
        number:
          min: 0
          max: 100
          step: 0.1
          mode: box
```

## Service Response

For services that return data:

```python
from homeassistant.core import ServiceResponse, SupportsResponse

async def async_my_service(call: ServiceCall) -> ServiceResponse:
    """Handle service with response."""
    result = await client.async_get_data()
    return {
        "status": result.status,
        "value": result.value,
    }

hass.services.async_register(
    DOMAIN,
    "my_service",
    async_my_service,
    schema=SERVICE_SCHEMA,
    supports_response=SupportsResponse.ONLY,  # or OPTIONAL
)
```

## Exemption for action-setup

If your integration doesn't register any custom actions:

```yaml
# quality_scale.yaml
rules:
  action-setup:
    status: exempt
    comment: Integration does not register custom actions.
```

## Related Skills

- `config-flow` - Services may need config entry validation
- `quality-scale` - action-setup is a Bronze requirement
- `write-tests` - Testing service actions
