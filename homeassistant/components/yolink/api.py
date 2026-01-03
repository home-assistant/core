"""API for yolink bound to Home Assistant OAuth or UAC."""

from aiohttp import ClientSession
from yolink.auth_mgr import YoLinkAuthMgr
from yolink.const import OAUTH2_TOKEN
from yolink.local_auth_mgr import YoLinkLocalAuthMgr

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


class UACAuth(YoLinkLocalAuthMgr):
    """Provide yolink authentication using UAC (User Access Credentials)."""

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        uaid: str,
        secret_key: str,
    ) -> None:
        """Initialize yolink UAC Auth."""
        self.hass = hass
        super().__init__(
            session=websession,
            token_url=OAUTH2_TOKEN,
            client_id=uaid,
            client_secret=secret_key,
        )
