"""The Samsung TV integration."""
from homeassistant.helpers import discovery

from .const import DOMAIN

SUPPORTED_DOMAINS = ["media_player"]


async def async_setup(hass, config):
    """Set up the Samsung TV integration."""
    for domain in SUPPORTED_DOMAINS:
        discovery.load_platform(hass, domain, DOMAIN, {}, config)

    return True
