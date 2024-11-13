"""API for Portainer bound to Home Assistant OAuth."""

import logging
from types import MappingProxyType
from typing import Any

from aiohttp import ClientSession
from aiotainer.auth import AbstractAuth

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Portainer authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        data: dict[str, Any] | MappingProxyType[str, Any],
    ) -> None:
        """Initialize Portainer auth."""
        self.data = data
        super().__init__(websession, data[CONF_URL])

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self.data[CONF_ACCESS_TOKEN]
