---
title: "Device actions"
sidebar_label: Actions
---

:::warning
We are currently exploring alternatives to device automations. Existing device automations will continue to work but new device automations won't be accepted.
:::

Device actions allow a user to have a device do something. Examples are to turn a light on or open a door.

Device actions are defined as dictionaries. These dictionaries are created by your integration and are passed to your integration to create a function that performs the action.

Device actions can be provided by the integration that provides the device (e.g. ZHA, deCONZ) or the entity integrations that the device has entities with (e.g. light, switch).
An example of the former could be to reboot the device, while an example of the latter could be to turn a light on.

If the action requires dynamic validation that the static `ACTION_SCHEMA` can't provide, it's possible to implement an `async_validate_action_config` function.

```py
async def async_validate_action_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
```

Home Assistant includes a template to get started with device actions. To get started, run inside a development environment `python3 -m script.scaffold device_action`.

The template will create a new file `device_action.py` in your integration folder and a matching test file. The file contains the following functions and constants:

#### `ACTION_SCHEMA`

This is the schema for actions. The base schema should be extended from `homeassistant.helpers.config_validation.DEVICE_ACTION_BASE_SCHEMA`. Do not apply the schema manually. The core will apply the schema if the action schema is defined as a constant in the `device_action.py` module of the integration.

#### `async_get_actions`

```py
async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions for devices."""
```

Return a list of actions that this device supports.

#### `async_call_action_from_config`

```py
async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
```

Execute the passed in action.
