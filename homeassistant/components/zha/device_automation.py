"""Provides device automations for ZHA devices that emit events."""
import voluptuous as vol

import homeassistant.components.automation.event as event

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE

from . import DOMAIN

CONF_SUBTYPE = "subtype"

CONF_SHORT_PRESS = "remote_button_short_press"
CONF_SHORT_RELEASE = "remote_button_short_release"
CONF_LONG_PRESS = "remote_button_long_press"
CONF_LONG_RELEASE = "remote_button_long_release"
CONF_DOUBLE_PRESS = "remote_button_double_press"
CONF_TRIPLE_PRESS = "remote_button_triple_press"
CONF_QUADRUPLE_PRESS = "remote_button_quadruple_press"
CONF_QUINTUPLE_PRESS = "remote_button_quintuple_press"
CONF_ROTATED = "device_rotated"
CONF_SHAKEN = "device_shaken"
CONF_DROPPED = "device_dropped"
CONF_SLID = "device_slid"
CONF_KNOCKED = "device_knocked"
CONF_FLIPPED = "device_flipped"

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
CONF_BUTTON_5 = "button_5"
CONF_BUTTON_6 = "button_6"

AQARA_ROUND_SWITCH_MODEL = "lumi.sensor_switch"
AQARA_ROUND_SWITCH = {
    (CONF_SHORT_PRESS, CONF_TURN_ON): {
        "command": "click",
        "args": {"click_type": "single"},
    },
    (CONF_DOUBLE_PRESS, CONF_TURN_ON): {
        "command": "click",
        "args": {"click_type": "double"},
    },
    (CONF_TRIPLE_PRESS, CONF_TURN_ON): {
        "command": "click",
        "args": {"click_type": "triple"},
    },
    (CONF_QUADRUPLE_PRESS, CONF_TURN_ON): {
        "command": "click",
        "args": {"click_type": "quadruple"},
    },
    (CONF_QUINTUPLE_PRESS, CONF_TURN_ON): {
        "command": "click",
        "args": {"click_type": "furious"},
    },
}

AQARA_CUBE_MODEL = "lumi.sensor_cube.aqgl01"
AQARA_CUBE = {
    (CONF_ROTATED, CONF_RIGHT): {"command": "rotate_right"},
    (CONF_ROTATED, CONF_LEFT): {"command": "rotate_left"},
    (CONF_SHAKEN, CONF_TURN_ON): {"command": "shake"},
    (CONF_DROPPED, CONF_TURN_ON): {"command": "drop"},
    (CONF_SLID, CONF_BUTTON_1): {"command": "slide", "args": {"activated_face": 1}},
    (CONF_SLID, CONF_BUTTON_2): {"command": "slide", "args": {"activated_face": 2}},
    (CONF_SLID, CONF_BUTTON_3): {"command": "slide", "args": {"activated_face": 3}},
    (CONF_SLID, CONF_BUTTON_4): {"command": "slide", "args": {"activated_face": 4}},
    (CONF_SLID, CONF_BUTTON_5): {"command": "slide", "args": {"activated_face": 5}},
    (CONF_SLID, CONF_BUTTON_6): {"command": "slide", "args": {"activated_face": 6}},
    (CONF_KNOCKED, CONF_BUTTON_1): {"command": "knock", "args": {"activated_face": 1}},
    (CONF_KNOCKED, CONF_BUTTON_2): {"command": "knock", "args": {"activated_face": 2}},
    (CONF_KNOCKED, CONF_BUTTON_3): {"command": "knock", "args": {"activated_face": 3}},
    (CONF_KNOCKED, CONF_BUTTON_4): {"command": "knock", "args": {"activated_face": 4}},
    (CONF_KNOCKED, CONF_BUTTON_5): {"command": "knock", "args": {"activated_face": 5}},
    (CONF_KNOCKED, CONF_BUTTON_6): {"command": "knock", "args": {"activated_face": 6}},
    (CONF_FLIPPED, CONF_BUTTON_1): {"command": "flip", "args": {"activated_face": 1}},
    (CONF_FLIPPED, CONF_BUTTON_2): {"command": "flip", "args": {"activated_face": 2}},
    (CONF_FLIPPED, CONF_BUTTON_3): {"command": "flip", "args": {"activated_face": 3}},
    (CONF_FLIPPED, CONF_BUTTON_4): {"command": "flip", "args": {"activated_face": 4}},
    (CONF_FLIPPED, CONF_BUTTON_5): {"command": "flip", "args": {"activated_face": 5}},
    (CONF_FLIPPED, CONF_BUTTON_6): {"command": "flip", "args": {"activated_face": 6}},
}

REMOTES = {AQARA_ROUND_SWITCH_MODEL: AQARA_ROUND_SWITCH, AQARA_CUBE_MODEL: AQARA_CUBE}

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


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])

    if device.model not in REMOTES and trigger not in REMOTES[device.model]:
        raise InvalidDeviceAutomationConfig

    trigger = REMOTES[device.model][trigger]

    state_config = {
        event.CONF_EVENT_TYPE: "zha_event",
        event.CONF_EVENT_DATA: {
            "device_ieee": list(list(device.identifiers)[0])[1],
            **trigger,
        },
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
