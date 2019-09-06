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
from .config_flow import configured_gateways
from .deconz_event import CONF_DECONZ_EVENT, CONF_UNIQUE_ID
from .gateway import get_gateway_from_config_entry

CONF_TURN_ON_SHORT_PRESS = "remote_button_turn_on_short_press"
CONF_TURN_ON_SHORT_RELEASE = "remote_button_turn_on_short_release"
CONF_TURN_ON_LONG_PRESS = "remote_button_turn_on_long_press"
CONF_TURN_ON_LONG_RELEASE = "remote_button_turn_on_long_release"
CONF_TURN_ON_DOUBLE_PRESS = "remote_button_turn_on_double_press"
CONF_TURN_ON_TRIPLE_PRESS = "remote_button_turn_on_triple_press"
CONF_TURN_ON_QUADRUPLE_PRESS = "remote_button_turn_on_quadruple_press"
CONF_TURN_ON_QUINTUPLE_PRESS = "remote_button_turn_on_quintuple_press"

CONF_DIM_UP_SHORT_PRESS = "remote_button_dim_up_short_press"
CONF_DIM_UP_SHORT_RELEASE = "remote_button_dim_up_short_release"
CONF_DIM_UP_LONG_PRESS = "remote_button_dim_up_long_press"
CONF_DIM_UP_LONG_RELEASE = "remote_button_dim_up_long_release"

CONF_DIM_DOWN_SHORT_PRESS = "remote_button_dim_down_short_press"
CONF_DIM_DOWN_SHORT_RELEASE = "remote_button_dim_down_short_release"
CONF_DIM_DOWN_LONG_PRESS = "remote_button_dim_down_long_press"
CONF_DIM_DOWN_LONG_RELEASE = "remote_button_dim_down_long_release"

CONF_TURN_OFF_SHORT_PRESS = "remote_button_turn_off_short_press"
CONF_TURN_OFF_SHORT_RELEASE = "remote_button_turn_off_short_release"
CONF_TURN_OFF_LONG_PRESS = "remote_button_turn_off_long_press"
CONF_TURN_OFF_LONG_RELEASE = "remote_button_turn_off_long_release"

CONF_LEFT_SHORT_PRESS = "remote_button_left_short_press"
CONF_LEFT_SHORT_RELEASE = "remote_button_left_short_release"
CONF_LEFT_LONG_PRESS = "remote_button_left_long_press"
CONF_LEFT_LONG_RELEASE = "remote_button_left_long_release"
CONF_LEFT_DOUBLE_PRESS = "remote_button_left_double_press"
CONF_LEFT_ROTATION = "remote_button_left_rotation"

CONF_RIGHT_SHORT_PRESS = "remote_button_right_short_press"
CONF_RIGHT_SHORT_RELEASE = "remote_button_right_short_release"
CONF_RIGHT_LONG_PRESS = "remote_button_right_long_press"
CONF_RIGHT_LONG_RELEASE = "remote_button_right_long_release"
CONF_RIGHT_DOUBLE_PRESS = "remote_button_right_double_press"
CONF_RIGHT_ROTATION = "remote_button_right_rotation"

CONF_SHAKE = "remote_gyro_activated"

HUE_DIMMER_REMOTE_MODEL = "RWL021"
HUE_DIMMER_REMOTE = {
    CONF_TURN_ON_SHORT_PRESS: 1000,
    CONF_TURN_ON_SHORT_RELEASE: 1002,
    CONF_TURN_ON_LONG_PRESS: 1001,
    CONF_TURN_ON_LONG_RELEASE: 1003,
    CONF_DIM_UP_SHORT_PRESS: 2000,
    CONF_DIM_UP_SHORT_RELEASE: 2002,
    CONF_DIM_UP_LONG_PRESS: 2001,
    CONF_DIM_UP_LONG_RELEASE: 2003,
    CONF_DIM_DOWN_SHORT_PRESS: 3000,
    CONF_DIM_DOWN_SHORT_RELEASE: 3002,
    CONF_DIM_DOWN_LONG_PRESS: 3001,
    CONF_DIM_DOWN_LONG_RELEASE: 3003,
    CONF_TURN_OFF_SHORT_PRESS: 4000,
    CONF_TURN_OFF_SHORT_RELEASE: 4002,
    CONF_TURN_OFF_LONG_PRESS: 4001,
    CONF_TURN_OFF_LONG_RELEASE: 4003,
}

TRADFRI_REMOTE_MODEL = "TRADFRI remote control"
TRADFRI_REMOTE = {
    CONF_TURN_ON_SHORT_PRESS: 1002,
    CONF_TURN_ON_LONG_PRESS: 1001,
    CONF_DIM_UP_SHORT_RELEASE: 2002,
    CONF_DIM_UP_LONG_PRESS: 2001,
    CONF_DIM_UP_LONG_RELEASE: 2003,
    CONF_DIM_DOWN_SHORT_RELEASE: 3002,
    CONF_DIM_DOWN_LONG_PRESS: 3001,
    CONF_DIM_DOWN_LONG_RELEASE: 3003,
    CONF_LEFT_SHORT_RELEASE: 4002,
    CONF_LEFT_LONG_PRESS: 4001,
    CONF_LEFT_LONG_RELEASE: 4003,
    CONF_RIGHT_SHORT_RELEASE: 5002,
    CONF_RIGHT_LONG_PRESS: 5001,
    CONF_RIGHT_LONG_RELEASE: 5003,
}

TRADFRI_WIRELESS_DIMMER_MODEL = "TRADFRI wireless dimmer"
TRADFRI_WIRELESS_DIMMER = {CONF_LEFT_ROTATION: 3002, CONF_RIGHT_ROTATION: 2002}

AQARA_DOUBLE_WALL_SWITCH_MODEL = "lumi.remote.b286acn01"
AQARA_DOUBLE_WALL_SWITCH = {
    CONF_LEFT_SHORT_PRESS: 1002,
    CONF_LEFT_LONG_PRESS: 1001,
    CONF_LEFT_DOUBLE_PRESS: 1004,
    CONF_RIGHT_SHORT_PRESS: 2002,
    CONF_RIGHT_LONG_PRESS: 2001,
    CONF_RIGHT_DOUBLE_PRESS: 2004,
}

AQARA_MINI_SWITCH_MODEL = "lumi.remote.b1acn01"
AQARA_MINI_SWITCH = {
    CONF_TURN_ON_SHORT_PRESS: 1002,
    CONF_TURN_ON_DOUBLE_PRESS: 1004,
    CONF_TURN_ON_LONG_PRESS: 1001,
    CONF_TURN_ON_LONG_RELEASE: 1003,
}

AQARA_ROUND_SWITCH_MODEL = "lumi.sensor_switch"
AQARA_ROUND_SWITCH = {
    CONF_TURN_ON_SHORT_PRESS: 1000,
    CONF_TURN_ON_SHORT_RELEASE: 1002,
    CONF_TURN_ON_DOUBLE_PRESS: 1004,
    CONF_TURN_ON_TRIPLE_PRESS: 1005,
    CONF_TURN_ON_QUADRUPLE_PRESS: 1006,
    CONF_TURN_ON_QUINTUPLE_PRESS: 1010,
    CONF_TURN_ON_LONG_PRESS: 1001,
    CONF_TURN_ON_LONG_RELEASE: 1003,
}

AQARA_SQUARE_SWITCH_MODEL = "lumi.sensor_switch.aq3"
AQARA_SQUARE_SWITCH = {
    CONF_TURN_ON_SHORT_PRESS: 1002,
    CONF_TURN_ON_DOUBLE_PRESS: 1004,
    CONF_TURN_ON_LONG_PRESS: 1001,
    CONF_TURN_ON_LONG_RELEASE: 1003,
    CONF_SHAKE: 1007,
}

REMOTES = {
    HUE_DIMMER_REMOTE_MODEL: HUE_DIMMER_REMOTE,
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
            vol.Required(CONF_UNIQUE_ID): str,
        }
    )
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    if device.model not in REMOTES and config[CONF_TYPE] not in REMOTES[device.model]:
        return

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

    deconz_config_entries = configured_gateways(hass)

    deconz_event = None
    for config_entry in deconz_config_entries.values():

        if deconz_event:
            break

        gateway = get_gateway_from_config_entry(hass, config_entry)
        for item in gateway.events:

            if device_id == item.device_id:
                deconz_event = item
                break

    if deconz_event is None:
        return

    triggers = []
    for trigger in REMOTES[device.model].keys():
        triggers.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_PLATFORM: "device",
                CONF_TYPE: trigger,
                CONF_UNIQUE_ID: deconz_event.serial,
            }
        )

    return triggers
