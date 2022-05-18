"""Provides device triggers for switches."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

TRIGGER_SCHEMA = vol.All(
    toggle_entity.TRIGGER_SCHEMA,
    vol.Schema({vol.Required(CONF_DOMAIN): DOMAIN}, extra=vol.ALLOW_EXTRA),
)


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


def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, str]]:
    """List device triggers."""
    return toggle_entity.async_get_triggers(hass, device_id, DOMAIN)


def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    return toggle_entity.async_get_trigger_capabilities(hass, config)
