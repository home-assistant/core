"""Provides device triggers for lutron caseta."""
import logging
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

_LOGGER = logging.getLogger(__name__)


SUPPORTED_INPUTS_EVENTS_TYPES = [ACTION_PRESS, ACTION_RELEASE]

LUTRON_BUTTON_TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(SUPPORTED_INPUTS_EVENTS_TYPES),
    }
)


PICO_REMOTE_2_BUTTON_TYPES = {
    "on": 2,
    "off": 4,
}
PICO_REMOTE_2_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_REMOTE_2_BUTTON_TYPES),
    }
)

PICO_REMOTE_3_BUTTON_TYPES = {
    "on": 2,
    "stop": 3,
    "off": 4,
    "raise": 5,
    "lower": 6,
}
PICO_REMOTE_3_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_REMOTE_3_BUTTON_TYPES),
    }
)

PICO_REMOTE_4_BUTTON_TYPES = {
    "button1": 8,
    "button2": 9,
    "button3": 10,
    "button4": 11,
}
PICO_REMOTE_4_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(PICO_REMOTE_4_BUTTON_TYPES),
    }
)

SHADE_REMOTE_BUTTON_TYPES = {
    "open_all": 1,
    "stop_all": 2,
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
SHADE_REMOTE_TRIGGER_SCHEMA = LUTRON_BUTTON_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_SUBTYPE): vol.In(SHADE_REMOTE_BUTTON_TYPES),
    }
)

PICO_REMOTE_2_MODELS = ("P", "2")  # PJ2-2B-GXX-X01
PICO_REMOTE_3_MODELS = ("P", "3")  # PJ2-3BRL-GXX-X01
PICO_REMOTE_4_MODELS = ("P", "4")  # PJ2-4B-GXX-X21
SHADE_REMOTE_MODELS = ("C", "Y")  # CS-YJ-4GC-WH

MODEL_SCHEMA_MAP = {
    PICO_REMOTE_2_MODELS: PICO_REMOTE_2_TRIGGER_SCHEMA,
    PICO_REMOTE_3_MODELS: PICO_REMOTE_3_TRIGGER_SCHEMA,
    PICO_REMOTE_4_MODELS: PICO_REMOTE_4_TRIGGER_SCHEMA,
    SHADE_REMOTE_MODELS: SHADE_REMOTE_TRIGGER_SCHEMA,
}


MODEL_SUBTYPE_MAP = {
    PICO_REMOTE_2_MODELS: PICO_REMOTE_2_BUTTON_TYPES,
    PICO_REMOTE_3_MODELS: PICO_REMOTE_3_BUTTON_TYPES,
    PICO_REMOTE_4_MODELS: PICO_REMOTE_4_BUTTON_TYPES,
    SHADE_REMOTE_MODELS: SHADE_REMOTE_BUTTON_TYPES,
}

TRIGGER_SCHEMA = vol.Any(
    PICO_REMOTE_2_TRIGGER_SCHEMA,
    PICO_REMOTE_3_TRIGGER_SCHEMA,
    PICO_REMOTE_4_TRIGGER_SCHEMA,
    SHADE_REMOTE_TRIGGER_SCHEMA,
)


async def async_validate_trigger_config(hass: HomeAssistant, config: ConfigType):
    """Validate config."""
    # if device is available verify parameters against device capabilities
    device = get_button_device_by_dr_id(hass, config[CONF_DEVICE_ID])

    if not device:
        return config

    device_model_tup = get_device_model_tuple(device)
    schema = MODEL_SCHEMA_MAP.get(device_model_tup)

    if not schema:
        return config

    return schema(config)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for lutron caseta devices."""
    triggers = []

    device = get_button_device_by_dr_id(hass, device_id)
    _LOGGER.debug("async_get_triggers: %s = %s", device_id, device)

    if not device:
        raise InvalidDeviceAutomationConfig(f"Device not found: {device_id}")

    device_model_tup = get_device_model_tuple(device)

    _LOGGER.debug("device_model_tup: %s = %s", device_id, device_model_tup)

    valid_buttons = MODEL_SUBTYPE_MAP.get(device_model_tup)
    _LOGGER.debug("valid_buttons: %s = %s", device_id, valid_buttons)

    if not valid_buttons:
        raise InvalidDeviceAutomationConfig(
            f"Device model {device['model']} not supported: {device_id}"
        )

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
    device_model_tup = get_device_model_tuple(device)
    schema = MODEL_SCHEMA_MAP.get(device_model_tup)
    config = schema(config)
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: LUTRON_CASETA_BUTTON_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                ATTR_SERIAL: device["serial"],
                ATTR_BUTTON_NUMBER: config[CONF_SUBTYPE],
                ATTR_ACTION: config[CONF_TYPE],
            },
        }
    )
    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    _LOGGER.debug("async_attach_trigger: %s %s", config, event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )


def get_button_device_by_dr_id(hass: HomeAssistant, device_id: str):
    """Get a lutron device for the given device id."""
    for config_entry in hass.data[DOMAIN]:
        button_devices = hass.data[DOMAIN][config_entry][BUTTON_DEVICES]
        device = button_devices.get(device_id)
        if device:
            return device

    return None


def get_device_model_tuple(device):
    """Return a lookup tuple for finding the schema for a device."""
    model_split = device["model"].split("-")

    base_model = model_split[0][:1]
    model_type = model_split[1][:1]

    return (base_model, model_type)
