"""Provides device triggers for lutron caseta."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    ACTION_PRESS,
    ACTION_RELEASE,
    ATTR_ACTION,
    ATTR_BUTTON_TYPE,
    CONF_SUBTYPE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
)
from .models import LutronCasetaData

_LOGGER = logging.getLogger(__name__)


def _reverse_dict(forward_dict: dict) -> dict:
    """Reverse a dictionary."""
    return {v: k for k, v in forward_dict.items()}


SUPPORTED_INPUTS_EVENTS_TYPES = [ACTION_PRESS, ACTION_RELEASE]

LUTRON_BUTTON_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(SUPPORTED_INPUTS_EVENTS_TYPES),
    }
)


KEYPAD_LEAP_BUTTON_NAME_OVERRIDE = {
    "RRD-W2RLD": {
        17: "raise_1",
        16: "lower_1",
        19: "raise_2",
        18: "lower_2",
    },
    "RRD-W1RLD": {
        19: "raise",
        18: "lower",
    },
}


PICO_2_BUTTON_BUTTON_TYPES_TO_LIP = {
    "on": 2,
    "off": 4,
}
PICO_2_BUTTON_BUTTON_TYPES_TO_LEAP = {
    "on": 0,
    "off": 2,
}
PICO_2_BUTTON_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_2_BUTTON_BUTTON_TYPES_TO_LIP),
    }
)


PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LIP = {
    "on": 2,
    "off": 4,
    "raise": 5,
    "lower": 6,
}
PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LEAP = {
    "on": 0,
    "off": 2,
    "raise": 3,
    "lower": 4,
}
PICO_2_BUTTON_RAISE_LOWER_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(
            PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LIP
        ),
    }
)


PICO_3_BUTTON_BUTTON_TYPES_TO_LIP = {
    "on": 2,
    "stop": 3,
    "off": 4,
}
PICO_3_BUTTON_BUTTON_TYPES_TO_LEAP = {
    "on": 0,
    "stop": 1,
    "off": 2,
}
PICO_3_BUTTON_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_3_BUTTON_BUTTON_TYPES_TO_LIP),
    }
)

PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LIP = {
    "on": 2,
    "stop": 3,
    "off": 4,
    "raise": 5,
    "lower": 6,
}
PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LEAP = {
    "on": 0,
    "stop": 1,
    "off": 2,
    "raise": 3,
    "lower": 4,
}
PICO_3_BUTTON_RAISE_LOWER_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(
            PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LIP
        ),
    }
)

PICO_4_BUTTON_BUTTON_TYPES_TO_LIP = {
    "button_1": 8,
    "button_2": 9,
    "button_3": 10,
    "button_4": 11,
}
PICO_4_BUTTON_BUTTON_TYPES_TO_LEAP = {
    "button_1": 1,
    "button_2": 2,
    "button_3": 3,
    "button_4": 4,
}
LEAP_TO_PICO_4_BUTTON_BUTTON_TYPES = {
    v: k for k, v in PICO_4_BUTTON_BUTTON_TYPES_TO_LEAP.items()
}
PICO_4_BUTTON_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_BUTTON_TYPES_TO_LIP),
    }
)


PICO_4_BUTTON_ZONE_BUTTON_TYPES_TO_LIP = {
    "on": 8,
    "raise": 9,
    "lower": 10,
    "off": 11,
}
PICO_4_BUTTON_ZONE_BUTTON_TYPES_TO_LEAP = {
    "on": 1,
    "raise": 2,
    "lower": 3,
    "off": 4,
}
LEAP_TO_PICO_4_BUTTON_ZONE_BUTTON_TYPES = {
    v: k for k, v in PICO_4_BUTTON_ZONE_BUTTON_TYPES_TO_LEAP.items()
}
PICO_4_BUTTON_ZONE_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_ZONE_BUTTON_TYPES_TO_LIP),
    }
)


PICO_4_BUTTON_SCENE_BUTTON_TYPES_TO_LIP = {
    "button_1": 8,
    "button_2": 9,
    "button_3": 10,
    "off": 11,
}
PICO_4_BUTTON_SCENE_BUTTON_TYPES_TO_LEAP = {
    "button_1": 1,
    "button_2": 2,
    "button_3": 3,
    "off": 4,
}
PICO_4_BUTTON_SCENE_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_SCENE_BUTTON_TYPES_TO_LIP),
    }
)


PICO_4_BUTTON_2_GROUP_BUTTON_TYPES_TO_LIP = {
    "group_1_button_1": 8,
    "group_1_button_2": 9,
    "group_2_button_1": 10,
    "group_2_button_2": 11,
}
PICO_4_BUTTON_2_GROUP_BUTTON_TYPES_TO_LEAP = {
    "group_1_button_1": 1,
    "group_1_button_2": 2,
    "group_2_button_1": 3,
    "group_2_button_2": 4,
}
PICO_4_BUTTON_2_GROUP_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_2_GROUP_BUTTON_TYPES_TO_LIP),
    }
)

FOUR_GROUP_REMOTE_BUTTON_TYPES_TO_LIP = {
    "open_all": 2,
    "stop_all": 3,
    "close_all": 4,
    "raise_all": 5,
    "lower_all": 6,
    "open_1": 10,
    "stop_1": 11,
    "close_1": 12,
    "raise_1": 13,
    "lower_1": 14,
    "open_2": 18,
    "stop_2": 19,
    "close_2": 20,
    "raise_2": 21,
    "lower_2": 22,
    "open_3": 26,
    "stop_3": 27,
    "close_3": 28,
    "raise_3": 29,
    "lower_3": 30,
    "open_4": 34,
    "stop_4": 35,
    "close_4": 36,
    "raise_4": 37,
    "lower_4": 38,
}
FOUR_GROUP_REMOTE_BUTTON_TYPES_TO_LEAP = {
    "open_all": 0,
    "stop_all": 1,
    "close_all": 2,
    "raise_all": 3,
    "lower_all": 4,
    "open_1": 5,
    "stop_1": 6,
    "close_1": 7,
    "raise_1": 8,
    "lower_1": 9,
    "open_2": 10,
    "stop_2": 11,
    "close_2": 12,
    "raise_2": 13,
    "lower_2": 14,
    "open_3": 15,
    "stop_3": 16,
    "close_3": 17,
    "raise_3": 18,
    "lower_3": 19,
    "open_4": 20,
    "stop_4": 21,
    "close_4": 22,
    "raise_4": 23,
    "lower_4": 24,
}
FOUR_GROUP_REMOTE_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(FOUR_GROUP_REMOTE_BUTTON_TYPES_TO_LIP),
    }
)


DEVICE_TYPE_SCHEMA_MAP = {
    "Pico2Button": PICO_2_BUTTON_TRIGGER_SCHEMA,
    "Pico2ButtonRaiseLower": PICO_2_BUTTON_RAISE_LOWER_TRIGGER_SCHEMA,
    "Pico3Button": PICO_3_BUTTON_TRIGGER_SCHEMA,
    "Pico3ButtonRaiseLower": PICO_3_BUTTON_RAISE_LOWER_TRIGGER_SCHEMA,
    "Pico4Button": PICO_4_BUTTON_TRIGGER_SCHEMA,
    "Pico4ButtonScene": PICO_4_BUTTON_SCENE_TRIGGER_SCHEMA,
    "Pico4ButtonZone": PICO_4_BUTTON_ZONE_TRIGGER_SCHEMA,
    "Pico4Button2Group": PICO_4_BUTTON_2_GROUP_TRIGGER_SCHEMA,
    "FourGroupRemote": FOUR_GROUP_REMOTE_TRIGGER_SCHEMA,
}

DEVICE_TYPE_SUBTYPE_MAP_TO_LIP = {
    "Pico2Button": PICO_2_BUTTON_BUTTON_TYPES_TO_LIP,
    "Pico2ButtonRaiseLower": PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LIP,
    "Pico3Button": PICO_3_BUTTON_BUTTON_TYPES_TO_LIP,
    "Pico3ButtonRaiseLower": PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LIP,
    "Pico4Button": PICO_4_BUTTON_BUTTON_TYPES_TO_LIP,
    "Pico4ButtonScene": PICO_4_BUTTON_SCENE_BUTTON_TYPES_TO_LIP,
    "Pico4ButtonZone": PICO_4_BUTTON_ZONE_BUTTON_TYPES_TO_LIP,
    "Pico4Button2Group": PICO_4_BUTTON_2_GROUP_BUTTON_TYPES_TO_LIP,
    "FourGroupRemote": FOUR_GROUP_REMOTE_BUTTON_TYPES_TO_LIP,
}

DEVICE_TYPE_SUBTYPE_MAP_TO_LEAP = {
    "Pico2Button": PICO_2_BUTTON_BUTTON_TYPES_TO_LEAP,
    "Pico2ButtonRaiseLower": PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LEAP,
    "Pico3Button": PICO_3_BUTTON_BUTTON_TYPES_TO_LEAP,
    "Pico3ButtonRaiseLower": PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES_TO_LEAP,
    "Pico4Button": PICO_4_BUTTON_BUTTON_TYPES_TO_LEAP,
    "Pico4ButtonScene": PICO_4_BUTTON_SCENE_BUTTON_TYPES_TO_LEAP,
    "Pico4ButtonZone": PICO_4_BUTTON_ZONE_BUTTON_TYPES_TO_LEAP,
    "Pico4Button2Group": PICO_4_BUTTON_2_GROUP_BUTTON_TYPES_TO_LEAP,
    "FourGroupRemote": FOUR_GROUP_REMOTE_BUTTON_TYPES_TO_LEAP,
}

LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP: dict[str, dict[int, str]] = {
    k: _reverse_dict(v) for k, v in DEVICE_TYPE_SUBTYPE_MAP_TO_LEAP.items()
}

TRIGGER_SCHEMA = vol.Any(
    PICO_2_BUTTON_TRIGGER_SCHEMA,
    PICO_3_BUTTON_RAISE_LOWER_TRIGGER_SCHEMA,
    PICO_4_BUTTON_TRIGGER_SCHEMA,
    PICO_4_BUTTON_SCENE_TRIGGER_SCHEMA,
    PICO_4_BUTTON_ZONE_TRIGGER_SCHEMA,
    PICO_4_BUTTON_2_GROUP_TRIGGER_SCHEMA,
    FOUR_GROUP_REMOTE_TRIGGER_SCHEMA,
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""

    device_id = config[CONF_DEVICE_ID]
    subtype = config[CONF_SUBTYPE]

    if not (data := get_lutron_data_by_dr_id(hass, device_id)) or not (
        keypad := data.keypad_data.dr_device_id_to_keypad.get(device_id)
    ):
        return config

    keypad_trigger_schemas = data.keypad_data.trigger_schemas
    keypad_button_names_to_leap = data.keypad_data.button_names_to_leap

    # Retrieve trigger schema, preferring hard-coded triggers from device_trigger.py
    if not (
        schema := DEVICE_TYPE_SCHEMA_MAP.get(
            keypad["type"],
            keypad_trigger_schemas.get(keypad["lutron_device_id"]),
        )
    ):
        # Trigger schema not found - log error
        _LOGGER.error(
            "Cannot validate trigger %s because the trigger schema was not found",
            config,
        )
        return config

    # Retrieve list of valid buttons, preferring hard-coded triggers from device_trigger.py
    device_type = keypad["type"]
    valid_buttons = DEVICE_TYPE_SUBTYPE_MAP_TO_LEAP.get(
        device_type,
        keypad_button_names_to_leap[keypad["lutron_device_id"]],
    )

    if subtype not in valid_buttons:
        # Trigger subtype is invalid - raise error
        _LOGGER.error(
            "Cannot validate trigger %s because subtype %s is invalid", config, subtype
        )
        return config

    return schema(config)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for lutron caseta devices."""
    # Check if device is a valid keypad.  Return empty if not.
    if not (data := get_lutron_data_by_dr_id(hass, device_id)) or not (
        keypad := data.keypad_data.dr_device_id_to_keypad.get(device_id)
    ):
        return []

    keypad_button_names_to_leap = data.keypad_data.button_names_to_leap

    # Retrieve list of valid buttons, preferring hard-coded triggers from device_trigger.py
    valid_buttons = DEVICE_TYPE_SUBTYPE_MAP_TO_LEAP.get(
        keypad["type"],
        keypad_button_names_to_leap[keypad["lutron_device_id"]],
    )

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger,
            CONF_SUBTYPE: subtype,
        }
        for trigger in SUPPORTED_INPUTS_EVENTS_TYPES
        for subtype in valid_buttons
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: LUTRON_CASETA_BUTTON_EVENT,
                event_trigger.CONF_EVENT_DATA: {
                    CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                    ATTR_ACTION: config[CONF_TYPE],
                    ATTR_BUTTON_TYPE: config[CONF_SUBTYPE],
                },
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )


def get_lutron_data_by_dr_id(hass: HomeAssistant, device_id: str):
    """Get a lutron integration data for the given device registry device id."""
    if DOMAIN not in hass.data:
        return None

    for entry_id in hass.data[DOMAIN]:
        data: LutronCasetaData = hass.data[DOMAIN][entry_id]
        if data.keypad_data.dr_device_id_to_keypad.get(device_id):
            return data
    return None
