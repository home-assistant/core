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
import homeassistant.helpers.config_validation as cv

from . import DOMAIN
from .gateway import get_gateway_from_config_entry


# mypy: allow-untyped-defs, no-check-untyped-defs

CONF_TURN_ON = "turn_on"
CONF_TURN_OFF = "turn_off"

HUE_DIMMER_REMOTE = {CONF_TURN_ON: 1002, CONF_TURN_OFF: 4002}


HUE_DIMMER_REMOTE_TRIGGERS = [
    {CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_TYPE: CONF_TURN_ON},
    {CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_TYPE: CONF_TURN_OFF},
]

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "device",
            vol.Optional(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): DOMAIN,
            vol.Required(CONF_EVENT): cv.entity_id,
            vol.Required(CONF_TYPE): str,
        }
    )
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    print("ATTACH", config, action, automation_info)

    trigger_type = config.get(CONF_TYPE)
    event_id = config.get("event")

    trigger = HUE_DIMMER_REMOTE[trigger_type]

    state_config = {
        event.CONF_EVENT_TYPE: "deconz_event",
        event.CONF_EVENT_DATA: {"id": event_id, "event": trigger},
    }

    return await event.async_trigger(hass, state_config, action, automation_info)


async def async_trigger(hass, config, action, automation_info):
    """Temporary so existing automation framework can be used for testing."""
    print("TRIGGER")
    return await async_attach_trigger(hass, config, action, automation_info)


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)

    entry = hass.config_entries.async_get_entry(next(iter(device.config_entries)))
    gateway = get_gateway_from_config_entry(hass, entry)

    deconz_event = None
    for item in gateway.events:
        if next(iter(device.connections))[1] == item._device.uniqueid.split("-", 1)[0]:
            deconz_event = item

    if deconz_event is not None:
        triggers = []

        if deconz_event._device.modelid == "RWL021":

            for trigger in HUE_DIMMER_REMOTE_TRIGGERS:
                trigger = dict(trigger)
                trigger.update(device_id=device_id, event=deconz_event.id)
                triggers.append(trigger)
            print("GET", triggers)
            return triggers
