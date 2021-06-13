"""The zodiac component."""
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): {}},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the zodiac component."""
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))

    return True
