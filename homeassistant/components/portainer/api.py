"""API for Husqvarna Automower bound to Home Assistant OAuth."""

import logging

from aiohttp import ClientSession
from aiotainer.auth import AbstractAuth

from homeassistant.const import CONF_ACCESS_TOKEN

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Husqvarna Automower authentication tied to an OAuth2 based config entry."""

    def __init__(self, websession: ClientSession, entry) -> None:
        """Initialize Husqvarna Automower auth."""
        self.entry = entry
        super().__init__(websession, entry.data["ip_address"])

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self.entry.data[CONF_ACCESS_TOKEN]
