"""API for Volvo bound to Home Assistant OAuth."""

import logging
from typing import cast

from aiohttp import ClientSession
from volvocarsapi.auth import AccessTokenManager

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.redact import async_redact_data

_LOGGER = logging.getLogger(__name__)
_TO_REDACT = ["access_token", "id_token", "refresh_token"]


class VolvoAuth(AccessTokenManager):
    """Provide Volvo authentication tied to an OAuth2 based config entry."""

    def __init__(self, websession: ClientSession, oauth_session: OAuth2Session) -> None:
        """Initialize Volvo auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        current_access_token = self._oauth_session.token["access_token"]
        current_refresh_token = self._oauth_session.token["refresh_token"]

        await self._oauth_session.async_ensure_token_valid()

        _LOGGER.debug(
            "Token: %s", async_redact_data(self._oauth_session.token, _TO_REDACT)
        )
        _LOGGER.debug(
            "Token changed: access %s, refresh %s",
            current_access_token != self._oauth_session.token["access_token"],
            current_refresh_token != self._oauth_session.token["refresh_token"],
        )

        return cast(str, self._oauth_session.token["access_token"])


class ConfigFlowVolvoAuth(AccessTokenManager):
    """Provide Volvo authentication before a ConfigEntry exists.

    This implementation directly provides the token without supporting refresh.
    """

    def __init__(self, websession: ClientSession, token: str) -> None:
        """Initialize ConfigFlowVolvoAuth."""
        super().__init__(websession)
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return the token for the Volvo API."""
        return self._token
