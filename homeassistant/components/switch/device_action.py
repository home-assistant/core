"""Provides device actions for switches."""
from typing import List
import voluptuous as vol

from homeassistant.core import HomeAssistant, Context
from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.helpers.typing import TemplateVarsType, ConfigType
from . import DOMAIN


ACTION_SCHEMA = toggle_entity.ACTION_SCHEMA.extend({vol.Required(CONF_DOMAIN): DOMAIN})


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context,
) -> None:
    """Change state based on configuration."""
    await toggle_entity.async_call_action_from_config(
        hass, config, variables, context, DOMAIN
    )


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions."""
    return await toggle_entity.async_get_actions(hass, device_id, DOMAIN)
