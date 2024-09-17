"""API for Husqvarna Automower bound to Home Assistant OAuth."""

import logging
from typing import cast

from aiotainer.auth import AbstractAuth
from aiohttp import ClientSession

from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Husqvarna Automower authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
    ) -> None:
        """Initialize Husqvarna Automower auth."""
        super().__init__(websession, "https://192.168.178.202:9443/api")

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return "ptr_xxx"
