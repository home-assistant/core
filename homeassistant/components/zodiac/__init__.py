"""The zodiac component."""
import voluptuous as vol

from homeassistant.core import HomeAssistant

DOMAIN = "zodiac"

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): {}},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the zodiac component."""
    return True
