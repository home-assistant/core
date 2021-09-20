"""API for Honeywell Lyric bound to Home Assistant OAuth."""
import logging
from typing import cast

from aiohttp import BasicAuth, ClientSession
from aiolyric.client import LyricClient

from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class ConfigEntryLyricClient(LyricClient):
    """Provide Honeywell Lyric authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Honeywell Lyric auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self):
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]


class LyricLocalOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """Lyric Local OAuth2 implementation."""

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        data["client_id"] = self.client_id

        if self.client_secret is not None:
            data["client_secret"] = self.client_secret

        headers = {
            "Authorization": BasicAuth(self.client_id, self.client_secret).encode(),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        resp = await session.post(self.token_url, headers=headers, data=data)
        resp.raise_for_status()
        return cast(dict, await resp.json())
