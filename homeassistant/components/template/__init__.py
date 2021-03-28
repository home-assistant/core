"""The template component."""
from homeassistant.helpers.reload import async_setup_reload_service

from .const import DOMAIN, PLATFORMS


async def async_setup(hass, config):
    """Set up the template integration."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    return True
