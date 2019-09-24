"""Provides device trigger for lights."""
import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from . import DOMAIN


TRIGGER_SCHEMA = toggle_entity.TRIGGER_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)
    return await toggle_entity.async_attach_trigger(
        hass, config, action, automation_info
    )


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    return await toggle_entity.async_get_triggers(hass, device_id, DOMAIN)
