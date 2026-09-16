"""Provides device triggers for update entities."""

import probatio

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

TRIGGER_SCHEMA = probatio.All(
    toggle_entity.TRIGGER_SCHEMA,
    probatio.Schema(
        {probatio.Required(CONF_DOMAIN): DOMAIN}, extra=probatio.ALLOW_EXTRA
    ),
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    return await toggle_entity.async_attach_trigger(hass, config, action, trigger_info)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers."""
    return await toggle_entity.async_get_triggers(hass, device_id, DOMAIN)


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, probatio.Schema]:
    """List trigger capabilities."""
    return await toggle_entity.async_get_trigger_capabilities(hass, config)
