"""Provides device automations for control of LG webOS Smart TV."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from . import trigger
from .const import DOMAIN
from .helpers import (
    async_get_client_wrapper_by_device_entry,
    async_get_device_entry_by_device_id,
    async_is_device_config_entry_not_loaded,
)
from .triggers.turn_on import PLATFORM_TYPE as TURN_ON_PLATFORM_TYPE

TRIGGER_TYPES = {TURN_ON_PLATFORM_TYPE}
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    try:
        if async_is_device_config_entry_not_loaded(hass, config[CONF_DEVICE_ID]):
            return config
    except ValueError as err:
        raise InvalidDeviceAutomationConfig(err) from err

    if config[CONF_TYPE] == TURN_ON_PLATFORM_TYPE:
        device_id = config[CONF_DEVICE_ID]
        try:
            device = async_get_device_entry_by_device_id(hass, device_id)
            async_get_client_wrapper_by_device_entry(hass, device)
        except ValueError as err:
            raise InvalidDeviceAutomationConfig(err) from err

    return config


async def async_get_triggers(
    _hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for device."""
    triggers = []
    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    triggers.append({**base_trigger, CONF_TYPE: TURN_ON_PLATFORM_TYPE})

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if (trigger_type := config[CONF_TYPE]) == TURN_ON_PLATFORM_TYPE:
        trigger_config = {
            CONF_PLATFORM: trigger_type,
            CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        }
        trigger_config = await trigger.async_validate_trigger_config(
            hass, trigger_config
        )
        return await trigger.async_attach_trigger(
            hass, trigger_config, action, automation_info
        )

    raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")
