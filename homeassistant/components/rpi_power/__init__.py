"""The rpi_power component."""
from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "rpi_power"


async def async_setup(hass, config):
    """Set up the rpi_power component."""
    await async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
    return True
