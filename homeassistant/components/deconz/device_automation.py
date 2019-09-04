"""Provides device automations for deconz events."""
import voluptuous as vol

import homeassistant.components.automation.event as event
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)

from . import DOMAIN
from .deconz_event import CONF_DECONZ_EVENT, CONF_UNIQUE_ID
from .gateway import get_gateway_from_config_entry


# mypy: allow-untyped-defs, no-check-untyped-defs

CONF_TURN_ON = "turn_on"
CONF_TURN_ON_HOLD = "turn_on_hold"
CONF_TURN_ON_LONG_RELEASE = "turn_on_long_release"

CONF_DIM_UP = "dim_up"
CONF_DIM_UP_HOLD = "dim_up_hold"
CONF_DIM_UP_LONG_RELEASE = "dim_up_long_release"

CONF_DIM_DOWN = "dim_down"
CONF_DIM_DOWN_HOLD = "dim_down_hold"
CONF_DIM_DOWN_LONG_RELEASE = "dim_down_long_release"

CONF_TURN_OFF = "turn_off"
CONF_TURN_OFF_HOLD = "turn_off_hold"
CONF_TURN_OFF_LONG_RELEASE = "turn_off_long_release"


HUE_DIMMER_REMOTE = {
    CONF_TURN_ON: 1002,
    CONF_TURN_ON_HOLD: 1001,
    CONF_TURN_ON_LONG_RELEASE: 1003,
    CONF_DIM_UP: 2002,
    CONF_DIM_UP_HOLD: 2001,
    CONF_DIM_UP_LONG_RELEASE: 2003,
    CONF_DIM_DOWN: 3002,
    CONF_DIM_DOWN_HOLD: 3001,
    CONF_DIM_DOWN_LONG_RELEASE: 3003,
    CONF_TURN_OFF: 4002,
    CONF_TURN_OFF_HOLD: 4001,
    CONF_TURN_OFF_LONG_RELEASE: 4003,
}

REMOTES = {"RWL021": HUE_DIMMER_REMOTE}

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): DOMAIN,
            vol.Required(CONF_UNIQUE_ID): str,
            vol.Required(CONF_PLATFORM): "device",
            vol.Required(CONF_TYPE): str,
        }
    )
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    trigger = REMOTES[device.model][config[CONF_TYPE]]

    event_id = config[CONF_UNIQUE_ID]

    state_config = {
        event.CONF_EVENT_TYPE: CONF_DECONZ_EVENT,
        event.CONF_EVENT_DATA: {CONF_UNIQUE_ID: event_id, CONF_EVENT: trigger},
    }

    return await event.async_trigger(hass, state_config, action, automation_info)


async def async_trigger(hass, config, action, automation_info):
    """Temporary so existing automation framework can be used for testing."""
    return await async_attach_trigger(hass, config, action, automation_info)


async def async_get_triggers(hass, device_id):
    """List device triggers.

    Make sure device is a supported remote model.
    Retrieve the deconz event object matching device entry.
    Generate device trigger list.
    """
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)

    if device.model not in REMOTES:
        return

    entry = hass.config_entries.async_get_entry(next(iter(device.config_entries)))
    gateway = get_gateway_from_config_entry(hass, entry)

    deconz_event = None
    for item in gateway.events:

        try:
            if next(val for _, val in device.connections if val == item.serial):
                deconz_event = item
                break

        except StopIteration:
            continue

    if deconz_event is None:
        return

    triggers = []

    remote = REMOTES[device.model]

    for trigger in remote.keys():
        triggers.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_UNIQUE_ID: deconz_event.serial,
                CONF_PLATFORM: "device",
                CONF_TYPE: trigger,
            }
        )

    return triggers
