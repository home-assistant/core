"""API for Google Nest Device Access bound to Home Assistant OAuth.

The auth object is used for two use cases:

  async_get_access_token:
      This relies on the logic in OAuth2Session to determine if the token is
      valid.  OAuth2Session manages the logic for checking expiration times
      and exchanging a refresh token for a new access token.  This is used when
      directly talking to the API from the python library.

  async_get_creds:
      This is used for the google pubsub subcriber, which supports its own
      OAuth token refresh logic in a background thread.
"""

import logging

from aiohttp import ClientSession
from google.oauth2.credentials import Credentials
from google_nest_sdm.auth import AbstractAuth

from homeassistant.helpers import config_entry_oauth2_flow

from .const import SDM_SCOPES

_LOGGER = logging.getLogger(__name__)

# See https://developers.google.com/nest/device-access/registration


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Google Nest Device Access authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        api_url: str,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        local_oauth: config_entry_oauth2_flow.LocalOAuth2Implementation,
    ):
        """Initialize Google Nest Device Access auth."""
        super().__init__(websession, api_url)
        self._oauth_session = oauth_session
        self._local_oauth = local_oauth

    async def async_get_access_token(self):
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]

    async def async_get_creds(self):
        """Return an OAuth credential that supports refresh."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        token = self._oauth_session.token
        _LOGGER.debug("Credentials for token: %s", token)
        return Credentials(
            token=token["access_token"],
            refresh_token=token["refresh_token"],
            token_uri=self._local_oauth.token_url,
            client_id=self._local_oauth.client_id,
            client_secret=self._local_oauth.client_secret,
            scopes=tuple(SDM_SCOPES),
        )
