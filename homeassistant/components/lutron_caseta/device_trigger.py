"""Provides device triggers for lutron caseta."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    ACTION_PRESS,
    ACTION_RELEASE,
    ATTR_ACTION,
    ATTR_BUTTON_NUMBER,
    ATTR_SERIAL,
    BUTTON_DEVICES,
    CONF_SUBTYPE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
)

SUPPORTED_INPUTS_EVENTS_TYPES = [ACTION_PRESS, ACTION_RELEASE]

LUTRON_BUTTON_TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(SUPPORTED_INPUTS_EVENTS_TYPES),
    }
)


PICO_2_BUTTON_BUTTON_TYPES = {
    "on": 2,
    "off": 4,
}
PICO_2_BUTTON_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_2_BUTTON_BUTTON_TYPES),
    }
)


PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES = {
    "on": 2,
    "off": 4,
    "raise": 5,
    "lower": 6,
}
PICO_2_BUTTON_RAISE_LOWER_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES),
    }
)


PICO_3_BUTTON_BUTTON_TYPES = {
    "on": 2,
    "stop": 3,
    "off": 4,
}
PICO_3_BUTTON_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_3_BUTTON_BUTTON_TYPES),
    }
)

PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES = {
    "on": 2,
    "stop": 3,
    "off": 4,
    "raise": 5,
    "lower": 6,
}
PICO_3_BUTTON_RAISE_LOWER_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES),
    }
)

PICO_4_BUTTON_BUTTON_TYPES = {
    "button_1": 8,
    "button_2": 9,
    "button_3": 10,
    "button_4": 11,
}
PICO_4_BUTTON_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_BUTTON_TYPES),
    }
)


PICO_4_BUTTON_ZONE_BUTTON_TYPES = {
    "on": 8,
    "raise": 9,
    "lower": 10,
    "off": 11,
}
PICO_4_BUTTON_ZONE_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_ZONE_BUTTON_TYPES),
    }
)


PICO_4_BUTTON_SCENE_BUTTON_TYPES = {
    "button_1": 8,
    "button_2": 9,
    "button_3": 10,
    "off": 11,
}
PICO_4_BUTTON_SCENE_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_SCENE_BUTTON_TYPES),
    }
)


PICO_4_BUTTON_2_GROUP_BUTTON_TYPES = {
    "group_1_button_1": 8,
    "group_1_button_2": 9,
    "group_2_button_1": 10,
    "group_2_button_2": 11,
}
PICO_4_BUTTON_2_GROUP_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_4_BUTTON_2_GROUP_BUTTON_TYPES),
    }
)

FOUR_GROUP_REMOTE_BUTTON_TYPES = {
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
FOUR_GROUP_REMOTE_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(FOUR_GROUP_REMOTE_BUTTON_TYPES),
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

DEVICE_TYPE_SUBTYPE_MAP = {
    "Pico2Button": PICO_2_BUTTON_BUTTON_TYPES,
    "Pico2ButtonRaiseLower": PICO_2_BUTTON_RAISE_LOWER_BUTTON_TYPES,
    "Pico3Button": PICO_3_BUTTON_BUTTON_TYPES,
    "Pico3ButtonRaiseLower": PICO_3_BUTTON_RAISE_LOWER_BUTTON_TYPES,
    "Pico4Button": PICO_4_BUTTON_BUTTON_TYPES,
    "Pico4ButtonScene": PICO_4_BUTTON_SCENE_BUTTON_TYPES,
    "Pico4ButtonZone": PICO_4_BUTTON_ZONE_BUTTON_TYPES,
    "Pico4Button2Group": PICO_4_BUTTON_2_GROUP_BUTTON_TYPES,
    "FourGroupRemote": FOUR_GROUP_REMOTE_BUTTON_TYPES,
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


async def async_validate_trigger_config(hass: HomeAssistant, config: ConfigType):
    """Validate config."""
    # if device is available verify parameters against device capabilities
    device = get_button_device_by_dr_id(hass, config[CONF_DEVICE_ID])

    if not device:
        return config

    schema = DEVICE_TYPE_SCHEMA_MAP.get(device["type"])

    if not schema:
        raise InvalidDeviceAutomationConfig(
            f"Device type {device['type']} not supported: {config[CONF_DEVICE_ID]}"
        )

    return schema(config)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for lutron caseta devices."""
    triggers = []

    device = get_button_device_by_dr_id(hass, device_id)
    if not device:
        raise InvalidDeviceAutomationConfig(f"Device not found: {device_id}")

    valid_buttons = DEVICE_TYPE_SUBTYPE_MAP.get(device["type"], [])

    for trigger in SUPPORTED_INPUTS_EVENTS_TYPES:
        for subtype in valid_buttons:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_TYPE: trigger,
                    CONF_SUBTYPE: subtype,
                }
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    device = get_button_device_by_dr_id(hass, config[CONF_DEVICE_ID])
    schema = DEVICE_TYPE_SCHEMA_MAP.get(device["type"])
    valid_buttons = DEVICE_TYPE_SUBTYPE_MAP.get(device["type"])
    config = schema(config)
    event_config = {
        event_trigger.CONF_PLATFORM: CONF_EVENT,
        event_trigger.CONF_EVENT_TYPE: LUTRON_CASETA_BUTTON_EVENT,
        event_trigger.CONF_EVENT_DATA: {
            ATTR_SERIAL: device["serial"],
            ATTR_BUTTON_NUMBER: valid_buttons[config[CONF_SUBTYPE]],
            ATTR_ACTION: config[CONF_TYPE],
        },
    }
    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )


def get_button_device_by_dr_id(hass: HomeAssistant, device_id: str):
    """Get a lutron device for the given device id."""
    if DOMAIN not in hass.data:
        return None

    for config_entry in hass.data[DOMAIN]:
        button_devices = hass.data[DOMAIN][config_entry][BUTTON_DEVICES]
        device = button_devices.get(device_id)
        if device:
            return device

    return None
