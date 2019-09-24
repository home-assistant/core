"""Provides device automations for switches."""
import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from . import DOMAIN


ACTION_SCHEMA = toggle_entity.ACTION_SCHEMA.extend({vol.Required(CONF_DOMAIN): DOMAIN})


async def async_call_action_from_config(hass, config, variables, context):
    """Change state based on configuration."""
    config = ACTION_SCHEMA(config)
    await toggle_entity.async_call_action_from_config(
        hass, config, variables, context, DOMAIN
    )


async def async_get_actions(hass, device_id):
    """List device actions."""
    return await toggle_entity.async_get_actions(hass, device_id, DOMAIN)
