"""API for yolink bound to Home Assistant OAuth."""
from asyncio import run_coroutine_threadsafe

from aiohttp import ClientSession

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

# TODO the following two API examples are based on our suggested best practices
# for libraries using OAuth2 with requests or aiohttp. Delete the one you won't use.
# For more info see the docs at https://developers.home-assistant.io/docs/api_lib_auth/#oauth2.


class AuthenticationManager:
    """YoLink API Authentication Manager."""

    def __init__(
        self,
        client_session: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ):
        """Init YoLink AuthenticationManager."""

        self.httpClientSession: ClientSession = client_session
        self.authSession = oauth_session

    def httpAuthHeader(self):
        """Build API Request header -> Auth."""

        access_token = self.authSession.token["access_token"]
        return f"Bearer {access_token}"

    async def check_and_refresh_token(self):
        """Check the token."""

        if not self.authSession.valid_token:
            await self.authSession.async_ensure_token_valid()
        return self.authSession.token["access_token"]


class ConfigEntryAuth(AuthenticationManager):
    """Provide yolink authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize yolink Auth."""

        self.hass = hass
        super().__init__(websession, oauth_session)

    def refresh_tokens(self) -> str:
        """Refresh and return new yolink tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.authSession.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.authSession.token["access_token"]


class AsyncConfigEntryAuth(AuthenticationManager):
    """Provide yolink authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize yolink auth."""

        super().__init__(websession, oauth_session)

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

        if not self.authSession.valid_token:
            await self.authSession.async_ensure_token_valid()

        return self.authSession.token["access_token"]
