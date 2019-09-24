"""Provides device triggers for switches."""
from typing import List
import voluptuous as vol

from homeassistant.core import HomeAssistant, CALLBACK_TYPE
from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.helpers.typing import ConfigType
from . import DOMAIN


TRIGGER_SCHEMA = toggle_entity.TRIGGER_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)
    return await toggle_entity.async_attach_trigger(
        hass, config, action, automation_info
    )


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers."""
    return await toggle_entity.async_get_triggers(hass, device_id, DOMAIN)
