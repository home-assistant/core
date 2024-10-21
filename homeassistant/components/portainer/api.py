"""API for Portainer bound to Home Assistant OAuth."""

import logging

from aiohttp import ClientSession
from aiotainer.auth import AbstractAuth

from homeassistant.const import CONF_ACCESS_TOKEN

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Portainer authentication tied to an OAuth2 based config entry."""

    def __init__(self, websession: ClientSession, entry) -> None:
        """Initialize Portainer auth."""
        self.entry = entry
        super().__init__(websession, entry.data["host"], entry.data["port"])

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self.entry.data[CONF_ACCESS_TOKEN]
