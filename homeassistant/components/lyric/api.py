"""API for Honeywell Lyric bound to Home Assistant OAuth."""

from typing import cast

from aiohttp import BasicAuth, ClientSession
from aiolyric.client import LyricClient

from homeassistant.components.application_credentials import AuthImplementation
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class OAuth2SessionLyric(config_entry_oauth2_flow.OAuth2Session):
    """OAuth2Session for Lyric."""

    async def force_refresh_token(self) -> None:
        """Force a token refresh."""
        new_token = await self.implementation.async_refresh_token(self.token)

        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, "token": new_token}
        )


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
        await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]


class LyricLocalOAuth2Implementation(
    AuthImplementation,
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
