"""API for Ekey Bionyx bound to Home Assistant OAuth."""

from typing import Any

from aiohttp import ClientSession
import ekey_bionyxpy

from .const import API_URL


class ConfigFlowEkeyApi(ekey_bionyxpy.AbstractAuth):
    """Ekey Bionyx authentication before a ConfigEntry exists.

    This implementation directly provides the token without supporting refresh.
    """

    def __init__(
        self,
        websession: ClientSession,
        token: dict[str, Any],
    ) -> None:
        """Initialize ConfigFlowEkeyApi."""
        super().__init__(websession, API_URL)
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return the token for the Ekey API."""
        return self._token["access_token"]
