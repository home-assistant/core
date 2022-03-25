"""API for yolink bound to Home Assistant OAuth."""
from asyncio import run_coroutine_threadsafe

from aiohttp import ClientSession
from yolink_client.yolink_auth_mgr import YoLinkAuthMgr

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


class AuthenticationManager(YoLinkAuthMgr):
    """YoLink API Authentication Manager."""

    def __init__(
        self,
        client_session: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Init YoLink AuthenticationManager."""
        super().__init__(client_session)
        self.oauth_session = oauth_session

    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token["access_token"]

    async def check_and_refresh_token(self):
        """Check the token."""
        if not self.oauth_session.valid_token:
            await self.oauth_session.async_ensure_token_valid()
        return self.access_token()


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
            self.oauth_session.async_ensure_token_valid(), self.hass.loop
        ).result()
        return self.oauth_session.token["access_token"]
