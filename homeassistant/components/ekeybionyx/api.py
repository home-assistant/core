"""API for Ekey Bionyx bound to Home Assistant OAuth."""

from typing import Any

from aiohttp import ClientSession
import ekey_bionyxpy

from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(ekey_bionyxpy.AbstractAuth):
    """Provide Ekey Bionyx authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Ekey Bionyx auth."""
        super().__init__(websession, "https://api.bionyx.io/3rd-party/api")
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]


class ConfigFlowEkeyApi(ekey_bionyxpy.AbstractAuth):
    """Profile fitbit authentication before a ConfigEntry exists.

    This implementation directly provides the token without supporting refresh.
    """

    def __init__(
        self,
        websession: ClientSession,
        token: dict[str, Any],
    ) -> None:
        """Initialize ConfigFlowFitbitApi."""
        super().__init__(websession, "https://api.bionyx.io/3rd-party/api")
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return the token for the Fitbit API."""
        return self._token["access_token"]
