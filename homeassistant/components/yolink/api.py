"""API for yolink."""

from aiohttp import ClientSession
from yolink.auth_mgr import YoLinkAuthMgr

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


class ConfigEntryAuth(YoLinkAuthMgr):
    """Provide yolink authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        oauth2Session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize yolink Auth."""
        self.hass = hass
        self.oauth_session = oauth2Session
        super().__init__(websession)

    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token["access_token"]

    async def check_and_refresh_token(self) -> str:
        """Check the token."""
        await self.oauth_session.async_ensure_token_valid()
        return self.access_token()


class StaticTokenAuth(YoLinkAuthMgr):
    """Provide yolink authentication with an already resolved access token."""

    def __init__(self, websession: ClientSession, access_token: str) -> None:
        """Initialize yolink static token Auth."""
        super().__init__(websession)
        self._access_token = access_token

    def access_token(self) -> str:
        """Return the access token."""
        return self._access_token

    async def check_and_refresh_token(self) -> str:
        """Return the access token, which cannot be refreshed."""
        return self._access_token
