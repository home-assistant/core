"""The NEW_NAME integration."""
import voluptuous as vol

from .const import DOMAIN


CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): {}})


async def async_setup(hass, config):
    """Set up the NEW_NAME integration."""
    return True
