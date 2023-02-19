"""Config helpers for Homecom."""
from homeassistant.core import callback
from homeassistant.helpers.storage import Store

from . import DOMAIN


class ConfigStore:
    """A configuration store for Homecom."""

    _STORAGE_VERSION = 1
    _STORAGE_KEY = DOMAIN
    STORE_ACCESS_TOKEN = "access_token"
    STORE_REFRESH_TOKEN = "refresh_token"

    def __init__(self, hass):
        """Initialize a configuration store."""
        self._data = {}
        self._hass = hass
        self._store = Store(hass, self._STORAGE_VERSION, self._STORAGE_KEY)

    @property
    def authorized(self):
        """Return authorization status."""
        return self._data[self.STORE_ACCESS_TOKEN]

    @callback
    def set_authorized(self, access_token, refresh_token):
        """Set authorization status."""
        if access_token != self._data.get(self.STORE_ACCESS_TOKEN):
            self._data[self.STORE_ACCESS_TOKEN] = access_token
            self._data[self.STORE_REFRESH_TOKEN] = refresh_token
            self._store.async_delay_save(lambda: self._data)

    async def async_load(self):
        """Load saved configuration from disk."""
        if data := await self._store.async_load():
            self._data = data
        else:
            self._data = {self.STORE_ACCESS_TOKEN: None, self.STORE_REFRESH_TOKEN: None}
