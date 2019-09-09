"""Provides device automations for deconz events."""
import voluptuous as vol

import homeassistant.components.automation.event as event

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
from .config_flow import configured_gateways
from .deconz_event import CONF_DECONZ_EVENT, CONF_UNIQUE_ID
from .gateway import get_gateway_from_config_entry

CONF_SUBTYPE = "subtype"

CONF_SHORT_PRESS = "remote_button_short_press"
CONF_SHORT_RELEASE = "remote_button_short_release"
CONF_LONG_PRESS = "remote_button_long_press"
CONF_LONG_RELEASE = "remote_button_long_release"
CONF_DOUBLE_PRESS = "remote_button_double_press"
CONF_TRIPLE_PRESS = "remote_button_triple_press"
CONF_QUADRUPLE_PRESS = "remote_button_quadruple_press"
CONF_QUINTUPLE_PRESS = "remote_button_quintuple_press"
CONF_ROTATED = "remote_button_rotated"
CONF_SHAKE = "remote_gyro_activated"

CONF_TURN_ON = "turn_on"
CONF_TURN_OFF = "turn_off"
CONF_DIM_UP = "dim_up"
CONF_DIM_DOWN = "dim_down"
CONF_LEFT = "left"
CONF_RIGHT = "right"
CONF_OPEN = "open"
CONF_CLOSE = "close"
CONF_BOTH_BUTTONS = "both_buttons"
CONF_BUTTON_1 = "button_1"
CONF_BUTTON_2 = "button_2"
CONF_BUTTON_3 = "button_3"
CONF_BUTTON_4 = "button_4"

HUE_DIMMER_REMOTE_MODEL = "RWL021"
HUE_DIMMER_REMOTE = {
    (CONF_SHORT_PRESS, CONF_TURN_ON): 1000,
    (CONF_SHORT_RELEASE, CONF_TURN_ON): 1002,
    (CONF_LONG_PRESS, CONF_TURN_ON): 1001,
    (CONF_LONG_RELEASE, CONF_TURN_ON): 1003,
    (CONF_SHORT_PRESS, CONF_DIM_UP): 2000,
    (CONF_SHORT_RELEASE, CONF_DIM_UP): 2002,
    (CONF_LONG_PRESS, CONF_DIM_UP): 2001,
    (CONF_LONG_RELEASE, CONF_DIM_UP): 2003,
    (CONF_SHORT_PRESS, CONF_DIM_DOWN): 3000,
    (CONF_SHORT_RELEASE, CONF_DIM_DOWN): 3002,
    (CONF_LONG_PRESS, CONF_DIM_DOWN): 3001,
    (CONF_LONG_RELEASE, CONF_DIM_DOWN): 3003,
    (CONF_SHORT_PRESS, CONF_TURN_OFF): 4000,
    (CONF_SHORT_RELEASE, CONF_TURN_OFF): 4002,
    (CONF_LONG_PRESS, CONF_TURN_OFF): 4001,
    (CONF_LONG_RELEASE, CONF_TURN_OFF): 4003,
}

HUE_TAP_REMOTE_MODEL = "ZGPSWITCH"
HUE_TAP_REMOTE = {
    (CONF_SHORT_PRESS, CONF_BUTTON_1): 34,
    (CONF_SHORT_PRESS, CONF_BUTTON_2): 16,
    (CONF_SHORT_PRESS, CONF_BUTTON_3): 17,
    (CONF_SHORT_PRESS, CONF_BUTTON_4): 18,
}

TRADFRI_ON_OFF_SWITCH_MODEL = "TRADFRI on/off switch"
TRADFRI_ON_OFF_SWITCH = {
    (CONF_SHORT_PRESS, CONF_TURN_ON): 1002,
    (CONF_LONG_PRESS, CONF_TURN_ON): 1001,
    (CONF_LONG_RELEASE, CONF_TURN_ON): 1003,
    (CONF_SHORT_PRESS, CONF_TURN_OFF): 2002,
    (CONF_LONG_PRESS, CONF_TURN_OFF): 2001,
    (CONF_LONG_RELEASE, CONF_TURN_OFF): 2003,
}

TRADFRI_OPEN_CLOSE_REMOTE_MODEL = "TRADFRI open/close remote"
TRADFRI_OPEN_CLOSE_REMOTE = {
    (CONF_SHORT_PRESS, CONF_OPEN): 1002,
    (CONF_LONG_PRESS, CONF_OPEN): 1003,
    (CONF_SHORT_PRESS, CONF_CLOSE): 2002,
    (CONF_LONG_PRESS, CONF_CLOSE): 2003,
}

TRADFRI_REMOTE_MODEL = "TRADFRI remote control"
TRADFRI_REMOTE = {
    (CONF_SHORT_PRESS, CONF_TURN_ON): 1002,
    (CONF_LONG_PRESS, CONF_TURN_ON): 1001,
    (CONF_SHORT_PRESS, CONF_DIM_UP): 2002,
    (CONF_LONG_PRESS, CONF_DIM_UP): 2001,
    (CONF_LONG_RELEASE, CONF_DIM_UP): 2003,
    (CONF_SHORT_PRESS, CONF_DIM_DOWN): 3002,
    (CONF_LONG_PRESS, CONF_DIM_DOWN): 3001,
    (CONF_LONG_RELEASE, CONF_DIM_DOWN): 3003,
    (CONF_SHORT_PRESS, CONF_LEFT): 4002,
    (CONF_LONG_PRESS, CONF_LEFT): 4001,
    (CONF_LONG_RELEASE, CONF_LEFT): 4003,
    (CONF_SHORT_PRESS, CONF_RIGHT): 5002,
    (CONF_LONG_PRESS, CONF_RIGHT): 5001,
    (CONF_LONG_RELEASE, CONF_RIGHT): 5003,
}

TRADFRI_WIRELESS_DIMMER_MODEL = "TRADFRI wireless dimmer"
TRADFRI_WIRELESS_DIMMER = {
    (CONF_ROTATED, CONF_LEFT): 3002,
    (CONF_ROTATED, CONF_RIGHT): 2002,
}

AQARA_DOUBLE_WALL_SWITCH_MODEL = "lumi.remote.b286acn01"
AQARA_DOUBLE_WALL_SWITCH = {
    (CONF_SHORT_PRESS, CONF_LEFT): 1002,
    (CONF_LONG_PRESS, CONF_LEFT): 1001,
    (CONF_DOUBLE_PRESS, CONF_LEFT): 1004,
    (CONF_SHORT_PRESS, CONF_RIGHT): 2002,
    (CONF_LONG_PRESS, CONF_RIGHT): 2001,
    (CONF_DOUBLE_PRESS, CONF_RIGHT): 2004,
    (CONF_SHORT_PRESS, CONF_BOTH_BUTTONS): 3002,
    (CONF_LONG_PRESS, CONF_BOTH_BUTTONS): 3001,
    (CONF_DOUBLE_PRESS, CONF_BOTH_BUTTONS): 3004,
}

AQARA_MINI_SWITCH_MODEL = "lumi.remote.b1acn01"
AQARA_MINI_SWITCH = {
    (CONF_SHORT_PRESS, CONF_TURN_ON): 1002,
    (CONF_DOUBLE_PRESS, CONF_TURN_ON): 1004,
    (CONF_LONG_PRESS, CONF_TURN_ON): 1001,
    (CONF_LONG_RELEASE, CONF_TURN_ON): 1003,
}

AQARA_ROUND_SWITCH_MODEL = "lumi.sensor_switch"
AQARA_ROUND_SWITCH = {
    (CONF_SHORT_PRESS, CONF_TURN_ON): 1000,
    (CONF_SHORT_RELEASE, CONF_TURN_ON): 1002,
    (CONF_DOUBLE_PRESS, CONF_TURN_ON): 1004,
    (CONF_TRIPLE_PRESS, CONF_TURN_ON): 1005,
    (CONF_QUADRUPLE_PRESS, CONF_TURN_ON): 1006,
    (CONF_QUINTUPLE_PRESS, CONF_TURN_ON): 1010,
    (CONF_LONG_PRESS, CONF_TURN_ON): 1001,
    (CONF_LONG_RELEASE, CONF_TURN_ON): 1003,
}

AQARA_SQUARE_SWITCH_MODEL = "lumi.sensor_switch.aq3"
AQARA_SQUARE_SWITCH = {
    (CONF_SHORT_PRESS, CONF_TURN_ON): 1002,
    (CONF_DOUBLE_PRESS, CONF_TURN_ON): 1004,
    (CONF_LONG_PRESS, CONF_TURN_ON): 1001,
    (CONF_LONG_RELEASE, CONF_TURN_ON): 1003,
    (CONF_SHAKE, ""): 1007,
}

REMOTES = {
    HUE_DIMMER_REMOTE_MODEL: HUE_DIMMER_REMOTE,
    HUE_TAP_REMOTE_MODEL: HUE_TAP_REMOTE,
    TRADFRI_ON_OFF_SWITCH_MODEL: TRADFRI_ON_OFF_SWITCH,
    TRADFRI_OPEN_CLOSE_REMOTE_MODEL: TRADFRI_OPEN_CLOSE_REMOTE,
    TRADFRI_REMOTE_MODEL: TRADFRI_REMOTE,
    TRADFRI_WIRELESS_DIMMER_MODEL: TRADFRI_WIRELESS_DIMMER,
    AQARA_DOUBLE_WALL_SWITCH_MODEL: AQARA_DOUBLE_WALL_SWITCH,
    AQARA_MINI_SWITCH_MODEL: AQARA_MINI_SWITCH,
    AQARA_ROUND_SWITCH_MODEL: AQARA_ROUND_SWITCH,
    AQARA_SQUARE_SWITCH_MODEL: AQARA_SQUARE_SWITCH,
}

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): DOMAIN,
            vol.Required(CONF_PLATFORM): "device",
            vol.Required(CONF_TYPE): str,
            vol.Required(CONF_SUBTYPE): str,
        }
    )
)


def _get_deconz_event_from_device_id(hass, device_id):
    """Resolve deconz event from device id."""
    deconz_config_entries = configured_gateways(hass)
    for config_entry in deconz_config_entries.values():

        gateway = get_gateway_from_config_entry(hass, config_entry)
        for deconz_event in gateway.events:

            if device_id == deconz_event.device_id:
                return deconz_event

    return None


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])

    if device.model not in REMOTES and trigger not in REMOTES[device.model]:
        raise InvalidDeviceAutomationConfig

    trigger = REMOTES[device.model][trigger]

    deconz_event = _get_deconz_event_from_device_id(hass, device.id)
    if deconz_event is None:
        raise InvalidDeviceAutomationConfig

    event_id = deconz_event.serial

    state_config = {
        event.CONF_EVENT_TYPE: CONF_DECONZ_EVENT,
        event.CONF_EVENT_DATA: {CONF_UNIQUE_ID: event_id, CONF_EVENT: trigger},
    }

    return await event.async_trigger(hass, state_config, action, automation_info)


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
