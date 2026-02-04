"""API for GitHub OAuth."""

from typing import cast

from aiogithubapi.device import GitHubDeviceAPI
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(GitHubDeviceAPI):
    """Provide GitHub authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize GitHub Auth."""
        self.hass = hass
        # Leaving out client_id as they are handled by Home Assistant
        super().__init__(
            client_id="",
            session=session,
        )
        self.session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        # Github CLI tokens do not expire, so no need to to valid_token
        return cast(str, self.session.token["access_token"])
