"""API for homelink bound to Home Assistant OAuth."""

from typing import cast, override

from aiohttp import ClientSession
from homelink.auth.abstract_auth import AbstractAuth
from homelink.settings import COGNITO_CLIENT_ID

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import OAUTH2_AUTHORIZE_URL, OAUTH2_TOKEN_URL


class HomeLinkOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """HomeLink OAuth2 implementation."""

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the HomeLink OAuth2 implementation."""
        super().__init__(
            hass,
            domain,
            COGNITO_CLIENT_ID,
            "",
            OAUTH2_AUTHORIZE_URL,
            OAUTH2_TOKEN_URL,
        )

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "HomeLink"


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide homelink authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize homelink auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])
