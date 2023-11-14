"""API for Netatmo bound to HASS OAuth."""
from typing import cast

from aiohttp import ClientSession
import pyatmo

from homeassistant.components import cloud
from homeassistant.helpers import config_entry_oauth2_flow
from .const import (
    API_SCOPES,
    API_SCOPES_EXCLUDED_FROM_CLOUD
)


def get_api_scopes(auth_implementation: str) -> set[str]:
    if auth_implementation == cloud.DOMAIN:
        return set({
            scope
            for scope in API_SCOPES
            if scope not in API_SCOPES_EXCLUDED_FROM_CLOUD
        })
    else:
        return set(API_SCOPES)


class AsyncConfigEntryNetatmoAuth(pyatmo.AbstractAsyncAuth):
    """Provide Netatmo authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize the auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token for Netatmo API."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token["access_token"])
