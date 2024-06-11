"""Router support for Tplink deco."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .errors import CannotLoginException

_LOGGER = logging.getLogger(__name__)

class tplinkDeco:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.device_name = "tplink-deco"
        self.track_devices = True

    async def async_setup(self) -> bool:
        """Set up the tplink deco."""
        return True

    async def async_get_status(self) -> dict:
        """Fetch the current status of the router."""
        return {"status": "ok"}
