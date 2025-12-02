"""Config storage for Mammotion integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN


class MammotionConfigStore(Store):
    """A configuration store for Alexa."""

    _STORAGE_VERSION = 1
    _STORAGE_MINOR_VERSION = 0
    _STORAGE_KEY = DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        version: int = _STORAGE_VERSION,
        minor_version: int = _STORAGE_MINOR_VERSION,
        key: str = _STORAGE_KEY,
    ) -> None:
        """Initialize the configuration store."""
        super().__init__(hass, version=version, minor_version=minor_version, key=key)
