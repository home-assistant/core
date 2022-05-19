"""Provides device automations for Fan."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import (
    GetAutomationCapabilitiesResult,
    GetAutomationsResult,
    toggle_entity,
)
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

TRIGGER_SCHEMA = vol.All(
    toggle_entity.TRIGGER_SCHEMA,
    vol.Schema({vol.Required(CONF_DOMAIN): DOMAIN}, extra=vol.ALLOW_EXTRA),
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> GetAutomationsResult:
    """List device triggers for Fan devices."""
    return await toggle_entity.async_get_triggers(hass, device_id, DOMAIN)


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> GetAutomationCapabilitiesResult:
    """List trigger capabilities."""
    return await toggle_entity.async_get_trigger_capabilities(hass, config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    return await toggle_entity.async_attach_trigger(
        hass, config, action, automation_info
    )
