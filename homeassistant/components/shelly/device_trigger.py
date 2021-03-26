"""Provides device triggers for Shelly."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    CONF_SUBTYPE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    INPUTS_EVENTS_SUBTYPES,
    SUPPORTED_INPUTS_EVENTS_TYPES,
)
from .utils import get_device_wrapper, get_input_triggers

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(SUPPORTED_INPUTS_EVENTS_TYPES),
        vol.Required(CONF_SUBTYPE): vol.In(INPUTS_EVENTS_SUBTYPES),
    }
)


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    # if device is available verify parameters against device capabilities
    wrapper = get_device_wrapper(hass, config[CONF_DEVICE_ID])
    if not wrapper:
        return config

    trigger = (config[CONF_TYPE], config[CONF_SUBTYPE])

    for block in wrapper.device.blocks:
        input_triggers = get_input_triggers(wrapper.device, block)
        if trigger in input_triggers:
            return config

    raise InvalidDeviceAutomationConfig(
        f"Invalid ({CONF_TYPE},{CONF_SUBTYPE}): {trigger}"
    )


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for Shelly devices."""
    triggers = []

    wrapper = get_device_wrapper(hass, device_id)
    if not wrapper:
        raise InvalidDeviceAutomationConfig(f"Device not found: {device_id}")

    for block in wrapper.device.blocks:
        input_triggers = get_input_triggers(wrapper.device, block)

        for trigger, subtype in input_triggers:
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
    event_config = {
        event_trigger.CONF_PLATFORM: CONF_EVENT,
        event_trigger.CONF_EVENT_TYPE: EVENT_SHELLY_CLICK,
        event_trigger.CONF_EVENT_DATA: {
            ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
            ATTR_CHANNEL: INPUTS_EVENTS_SUBTYPES[config[CONF_SUBTYPE]],
            ATTR_CLICK_TYPE: config[CONF_TYPE],
        },
    }
    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
