"""API for Google Nest Device Access bound to Home Assistant OAuth."""

import datetime
from typing import cast

from aiohttp import ClientSession
from google.oauth2.credentials import Credentials
from google_nest_sdm.auth import AbstractAuth

from homeassistant.helpers import config_entry_oauth2_flow

from .const import API_URL, OAUTH2_TOKEN, SDM_SCOPES

# See https://developers.google.com/nest/device-access/registration


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Google Nest Device Access authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize Google Nest Device Access auth."""
        super().__init__(websession, API_URL)
        self._oauth_session = oauth_session
        self._client_id = client_id
        self._client_secret = client_secret

    async def async_get_access_token(self) -> str:
        """Return a valid access token for SDM API."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token["access_token"])

    async def async_get_creds(self) -> Credentials:
        """Return an OAuth credential for Pub/Sub Subscriber."""
        # We don't have a way for Home Assistant to refresh creds on behalf
        # of the google pub/sub subscriber. Instead, build a full
        # Credentials object with enough information for the subscriber to
        # handle this on its own. We purposely don't refresh the token here
        # even when it is expired to fully hand off this responsibility and
        # know it is working at startup (then if not, fail loudly).
        token = self._oauth_session.token
        creds = Credentials(
            token=token["access_token"],
            refresh_token=token["refresh_token"],
            token_uri=OAUTH2_TOKEN,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=SDM_SCOPES,
        )
        creds.expiry = datetime.datetime.fromtimestamp(token["expires_at"])
        return creds
