"""Provides device actions for switches."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

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


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions."""
    return await toggle_entity.async_get_actions(hass, device_id, DOMAIN)
