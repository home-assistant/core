"""Provides device automations for lights."""
import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from . import DOMAIN


# mypy: allow-untyped-defs, no-check-untyped-defs

ACTION_SCHEMA = toggle_entity.ACTION_SCHEMA.extend({vol.Required(CONF_DOMAIN): DOMAIN})

CONDITION_SCHEMA = toggle_entity.CONDITION_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)

TRIGGER_SCHEMA = toggle_entity.TRIGGER_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)


async def async_call_action_from_config(hass, config, variables, context):
    """Change state based on configuration."""
    config = ACTION_SCHEMA(config)
    await toggle_entity.async_call_action_from_config(
        hass, config, variables, context, DOMAIN
    )


def async_condition_from_config(config, config_validation):
    """Evaluate state based on configuration."""
    config = CONDITION_SCHEMA(config)
    return toggle_entity.async_condition_from_config(config, config_validation)


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)
    return await toggle_entity.async_attach_trigger(
        hass, config, action, automation_info
    )


async def async_get_actions(hass, device_id):
    """List device actions."""
    return await toggle_entity.async_get_actions(hass, device_id, DOMAIN)


async def async_get_conditions(hass, device_id):
    """List device conditions."""
    return await toggle_entity.async_get_conditions(hass, device_id, DOMAIN)


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    return await toggle_entity.async_get_triggers(hass, device_id, DOMAIN)
