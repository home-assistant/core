"""Provides device automations for deconz events."""
import voluptuous as vol

import homeassistant.components.automation.state as state
from homeassistant.core import split_entity_id
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv

from . import DOMAIN
from .gateway import get_gateway_from_config_entry


# mypy: allow-untyped-defs, no-check-untyped-defs

CONF_TURN_OFF = "turn_off"
CONF_TURN_ON = "turn_on"

ENTITY_TRIGGERS = [
    {
        # Trigger when light is turned on
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: CONF_TURN_OFF,
    },
    {
        # Trigger when light is turned off
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: CONF_TURN_ON,
    },
]

HUE_DIMMER_REMOTE_TRIGGERS = [
    {
        # Trigger when remote button on is pressed
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: 1002,
    },
    {
        # Trigger when remote button off is pressed
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: 4002,
    },
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


def _is_domain(entity, domain):
    return split_entity_id(entity.entity_id)[0] == domain


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    trigger_type = config.get(CONF_TYPE)
    if trigger_type == CONF_TURN_ON:
        from_state = "off"
        to_state = "on"
    else:
        from_state = "on"
        to_state = "off"
    state_config = {
        state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_FROM: from_state,
        state.CONF_TO: to_state,
    }

    return await state.async_trigger(hass, state_config, action, automation_info)


async def async_trigger(hass, config, action, automation_info):
    """Temporary so existing automation framework can be used for testing."""
    return await async_attach_trigger(hass, config, action, automation_info)


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)

    entry = hass.config_entries.async_get_entry(next(iter(device.config_entries)))
    gateway = get_gateway_from_config_entry(hass, entry)

    event_trigger = None
    for event in gateway.events:
        if next(iter(device.connections))[1] == event._device.uniqueid.split("-", 1)[0]:
            event_trigger = event

    if event_trigger is not None:
        print("NO EVENT")
        triggers = []
        if event_trigger._device.modelid == "RWL021":
            for trigger in HUE_DIMMER_REMOTE_TRIGGERS:
                print(trigger)
                trigger = dict(trigger)
                trigger.update(device_id=device_id, event=event_trigger.id)
                triggers.append(trigger)
            print("TRIGGERS", triggers)
            return triggers
