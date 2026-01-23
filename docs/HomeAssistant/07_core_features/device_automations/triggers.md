---
title: "Device triggers"
sidebar_label: Triggers
---

:::warning
We are currently exploring alternatives to device automations. Existing device automations will continue to work but new device automations won't be accepted.
:::

Device triggers are automation triggers that are tied to a specific device and an event or state change. Examples are "light turned on" or "water detected".

Device triggers can be provided by the integration that provides the device (e.g. ZHA, deCONZ) or the entity integrations that the device has entities with (e.g. light, switch). An example of the former is events not tied to an entity e.g. key press on a remote control or touch panel, while an example of the latter could be that a light has been turned on.

To add support for Device Triggers, an integration needs to have a `device_trigger.py` and:

- *Define a `TRIGGER_SCHEMA`*: A dictionary that represents a trigger, such as a device and an event type
- *Create triggers*: Create dictionaries containing the device or entity and supported events or state changes as defined by the schema.
- *Attach triggers*: Associate a trigger config with an event or state change, e.g. a message fired on the event bus.
- *Add text and translations*: Give each trigger a human readable name.

Do not apply the static schema manually. The core will apply the schema if the trigger schema is defined as a constant in the `device_trigger.py` module of the integration.

If the trigger requires dynamic validation that the static `TRIGGER_SCHEMA` can't provide, it's possible to implement an `async_validate_trigger_config` function.

```py
async def async_validate_trigger_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
```

Home Assistant includes a template to get started with device triggers. To get started, run inside a development environment `python3 -m script.scaffold device_trigger`.

The template will create a new file `device_trigger.py` in your integration folder and a matching test file. The file contains the following functions and constants:


#### Define a `TRIGGER_SCHEMA`

Device triggers are defined as dictionaries. These dictionaries are created by your integration and are consumed by your integration to attach the trigger.

This is a voluptuous schema that verifies that a specific trigger dictionary represents a config that your integration can handle. This should extend the TRIGGER_BASE_SCHEMA from `device_automation/__init__.py`.

```python
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_TYPE,
)

TRIGGER_TYPES = {"water_detected", "noise_detected"}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)
```

This example has a single `type` field indicating the type of events supported.

#### Create triggers

The `async_get_triggers` method returns a list of triggers supported by the device or any associated entities. These are the triggers exposed to the user for creating automations.

```python
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.helpers import device_registry as dr

async def async_get_triggers(hass, device_id):
    """Return a list of triggers."""

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    triggers = []

    # Determine which triggers are supported by this device_id ...

    triggers.append({
        # Required fields of TRIGGER_BASE_SCHEMA
        CONF_PLATFORM: "device",
        CONF_DOMAIN: "mydomain",
        CONF_DEVICE_ID: device_id,
        # Required fields of TRIGGER_SCHEMA
        CONF_TYPE: "water_detected",
    })

    return triggers
```

#### Attach triggers

To wire it up: Given a `TRIGGER_SCHEMA` config, make sure the `action` is called when the trigger is triggered.

For example, you might attach the trigger and action to [Events fired](integration_events.md) on the event bus by your integration.

```python
async def async_attach_trigger(hass, config, action, trigger_info):
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: "mydomain_event",
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
```

The return value is a function that detaches the trigger.

#### Add text and translations

The Automation user interface will display a human-readable string in the device automation mapped to the event type.  Update `strings.json` with the trigger types and subtypes that you support:

```json
{
   "device_automation": {
    "trigger_type": {
      "water_detected": "Water detected",
      "noise_detected": "Noise detected"
    }
}
```

To test your translations during development, run `python3 -m script.translations develop`.

