"""API for Google Nest Device Access bound to Home Assistant OAuth."""

from aiohttp import ClientSession
from google.oauth2.credentials import Credentials
from google_nest_sdm.auth import AbstractAuth

from homeassistant.helpers import config_entry_oauth2_flow

# See https://developers.google.com/nest/device-access/registration


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Google Nest Device Access authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        api_url: str,
    ):
        """Initialize Google Nest Device Access auth."""
        super().__init__(websession, api_url)
        self._oauth_session = oauth_session

    async def async_get_access_token(self):
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]

    async def async_get_creds(self):
        """Return a minimal OAuth credential."""
        token = await self.async_get_access_token()
        return Credentials(token=token)
