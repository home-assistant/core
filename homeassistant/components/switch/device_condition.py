"""Provides device automations for switches."""
import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from . import DOMAIN


CONDITION_SCHEMA = toggle_entity.CONDITION_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)


def async_condition_from_config(config, config_validation):
    """Evaluate state based on configuration."""
    config = CONDITION_SCHEMA(config)
    return toggle_entity.async_condition_from_config(config, config_validation)


async def async_get_conditions(hass, device_id):
    """List device conditions."""
    return await toggle_entity.async_get_conditions(hass, device_id, DOMAIN)
