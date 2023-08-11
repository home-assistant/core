"""API for YouTube bound to Home Assistant OAuth."""
from youtubeaio.types import AuthScope
from youtubeaio.youtube import YouTube

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class AsyncConfigEntryAuth:
    """Provide Google authentication tied to an OAuth2 based config entry."""

    youtube: YouTube | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize YouTube Auth."""
        self.oauth_session = oauth2_session
        self.hass = hass

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token[CONF_ACCESS_TOKEN]

    async def check_and_refresh_token(self) -> str:
        """Check the token."""
        await self.oauth_session.async_ensure_token_valid()
        return self.access_token

    async def get_resource(self) -> YouTube:
        """Create resource."""
        token = await self.check_and_refresh_token()
        if self.youtube is None:
            self.youtube = YouTube(session=async_get_clientsession(self.hass))
        await self.youtube.set_user_authentication(token, [AuthScope.READ_ONLY])
        return self.youtube
