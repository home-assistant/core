"""Provides device automations for Philips Hue events."""
import logging

import voluptuous as vol

import homeassistant.components.automation.event as event
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)

from . import DOMAIN
from .hue_event import CONF_HUE_EVENT, CONF_UNIQUE_ID

_LOGGER = logging.getLogger(__file__)

CONF_SUBTYPE = "subtype"

CONF_SHORT_PRESS = "remote_button_short_press"
CONF_SHORT_RELEASE = "remote_button_short_release"
CONF_LONG_RELEASE = "remote_button_long_release"

CONF_TURN_ON = "turn_on"
CONF_TURN_OFF = "turn_off"
CONF_DIM_UP = "dim_up"
CONF_DIM_DOWN = "dim_down"
CONF_BUTTON_1 = "button_1"
CONF_BUTTON_2 = "button_2"
CONF_BUTTON_3 = "button_3"
CONF_BUTTON_4 = "button_4"


HUE_DIMMER_REMOTE_MODEL = "Hue dimmer switch"  # RWL020/021
HUE_DIMMER_REMOTE = {
    (CONF_SHORT_RELEASE, CONF_TURN_ON): {CONF_EVENT: 1002},
    (CONF_LONG_RELEASE, CONF_TURN_ON): {CONF_EVENT: 1003},
    (CONF_SHORT_RELEASE, CONF_DIM_UP): {CONF_EVENT: 2002},
    (CONF_LONG_RELEASE, CONF_DIM_UP): {CONF_EVENT: 2003},
    (CONF_SHORT_RELEASE, CONF_DIM_DOWN): {CONF_EVENT: 3002},
    (CONF_LONG_RELEASE, CONF_DIM_DOWN): {CONF_EVENT: 3003},
    (CONF_SHORT_RELEASE, CONF_TURN_OFF): {CONF_EVENT: 4002},
    (CONF_LONG_RELEASE, CONF_TURN_OFF): {CONF_EVENT: 4003},
}

HUE_TAP_REMOTE_MODEL = "Hue tap switch"  # ZGPSWITCH
HUE_TAP_REMOTE = {
    (CONF_SHORT_PRESS, CONF_BUTTON_1): {CONF_EVENT: 34},
    (CONF_SHORT_PRESS, CONF_BUTTON_2): {CONF_EVENT: 16},
    (CONF_SHORT_PRESS, CONF_BUTTON_3): {CONF_EVENT: 17},
    (CONF_SHORT_PRESS, CONF_BUTTON_4): {CONF_EVENT: 18},
}

REMOTES = {
    HUE_DIMMER_REMOTE_MODEL: HUE_DIMMER_REMOTE,
    HUE_TAP_REMOTE_MODEL: HUE_TAP_REMOTE,
}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): str, vol.Required(CONF_SUBTYPE): str}
)


def _get_hue_event_from_device_id(hass, device_id):
    """Resolve hue event from device id."""
    for bridge in hass.data.get(DOMAIN, {}).values():
        for hue_event in bridge.sensor_manager.current_events.values():
            if device_id == hue_event.device_registry_id:
                return hue_event

    return None


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])

    if (
        not device
        or device.model not in REMOTES
        or trigger not in REMOTES[device.model]
    ):
        raise InvalidDeviceAutomationConfig

    return config


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    hue_event = _get_hue_event_from_device_id(hass, device.id)
    if hue_event is None:
        raise InvalidDeviceAutomationConfig

    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])

    trigger = REMOTES[device.model][trigger]

    event_config = {
        event.CONF_PLATFORM: "event",
        event.CONF_EVENT_TYPE: CONF_HUE_EVENT,
        event.CONF_EVENT_DATA: {CONF_UNIQUE_ID: hue_event.unique_id, **trigger},
    }

    event_config = event.TRIGGER_SCHEMA(event_config)
    return await event.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )


async def async_get_triggers(hass, device_id):
    """List device triggers.

    Make sure device is a supported remote model.
    Retrieve the hue event object matching device entry.
    Generate device trigger list.
    """
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)

    if device.model not in REMOTES:
        return

    triggers = []
    for trigger, subtype in REMOTES[device.model].keys():
        triggers.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_PLATFORM: "device",
                CONF_TYPE: trigger,
                CONF_SUBTYPE: subtype,
            }
        )

    return triggers
