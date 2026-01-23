---
title: "Device conditions"
sidebar_label: Conditions
---

:::warning
We are currently exploring alternatives to device automations. Existing device automations will continue to work but new device automations won't be accepted.
:::

Device conditions allow a user to check if a certain condition is met. Examples are is a light on or is the floor wet.

Device conditions are defined as dictionaries. These dictionaries are created by your integration and are passed to your integration to create a function that checks the condition.

Device conditions can be provided by the integration that provides the device (e.g. ZHA, deCONZ) or the entity integrations that the device has entities with (e.g. light, humidity sensor).
An example of the latter could be to check if a light is on or the floor is wet.

If the condition requires dynamic validation that the static `CONDITION_SCHEMA` can't provide, it's possible to implement an `async_validate_condition_config` function.

```py
async def async_validate_condition_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
```

Home Assistant includes a template to get started with device conditions. To get started, run inside a development environment `python3 -m script.scaffold device_condition`.

The template will create a new file `device_condition.py` in your integration folder and a matching test file. The file contains the following functions and constants:

#### `CONDITION_SCHEMA`

This is the schema for conditions. The base schema should be extended from `homeassistant.helpers.config_validation.DEVICE_CONDITION_BASE_SCHEMA`.

#### `async_get_conditions`

```py
async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for devices."""
```

Return a list of conditions that this device supports.

#### `async_condition_from_config`

```py
@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
```

Create a condition function from a function. The condition functions should be an async-friendly callback that evaluates the condition and returns a `bool`.

The `config_validation` parameter will be used by the core to apply config validation conditionally with the defined `CONDITION_SCHEMA`.
