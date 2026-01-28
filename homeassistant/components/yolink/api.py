"""API for yolink."""

from __future__ import annotations

import logging
import time

from aiohttp import ClientError, ClientSession
from yolink.auth_mgr import YoLinkAuthMgr
from yolink.const import OAUTH2_TOKEN
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

_LOGGER = logging.getLogger(__name__)


class ConfigEntryAuth(YoLinkAuthMgr):
    """Provide yolink authentication tied to an OAuth2 based config entry.

    Implementation Notes (yolink-api 0.5.9):
    - Uses YoLinkAuthMgr base class for OAuth2 token management.
    - Token refresh is handled by Home Assistant's OAuth2Session.
    - access_token() must be a method (not property) because the library
      calls it as self.access_token() in http_auth_header().
    """

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize yolink Auth."""
        self.hass = hass
        self._oauth_session = oauth_session
        self._session = websession
        self._token_url = OAUTH2_TOKEN

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]

    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._oauth_session.token.get("access_token")

    async def check_and_refresh_token(self) -> None:
        """Check and refresh the token if needed."""
        await self._oauth_session.async_ensure_token_valid()


class UACAuth(YoLinkAuthMgr):
    """Provide yolink authentication using UAC credentials.

    Implementation Notes (yolink-api 0.5.9):
    - Uses YoLinkAuthMgr base class because YoLinkLocalAuthMgr is not available
      in yolink-api 0.5.9. Future versions may have YoLinkLocalAuthMgr which
      handles token fetching automatically.
    - access_token() must be a method (not property) because the library calls
      it as self.access_token() in http_auth_header().
    - Token fetching is implemented manually via _fetch_token() using the
      client_credentials OAuth2 grant type.

    For yolink-api >= 0.6.0 (if YoLinkLocalAuthMgr becomes available):
    - Consider switching to YoLinkLocalAuthMgr as base class
    - Remove manual token fetching logic
    - Update to use super().__init__() with token_url, client_id, client_secret
    """

    # Token buffer: refresh 5 minutes before expiration
    TOKEN_EXPIRY_BUFFER = 300

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        uaid: str,
        secret_key: str,
    ) -> None:
        """Initialize yolink UAC Auth."""
        self.hass = hass
        self._uaid = uaid
        self._secret_key = secret_key
        self._access_token: str | None = None
        self._token_expiry: float = 0  # Unix timestamp when token expires
        self._session = websession
        self._token_url = OAUTH2_TOKEN

    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    def _is_token_valid(self) -> bool:
        """Check if the current token is still valid."""
        if self._access_token is None:
            return False
        # Refresh if token expires within buffer time
        return time.time() < (self._token_expiry - self.TOKEN_EXPIRY_BUFFER)

    async def check_and_refresh_token(self) -> None:
        """Check and refresh the token if needed."""
        if not self._is_token_valid():
            await self._fetch_token()

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._is_token_valid():
            await self._fetch_token()
        assert self._access_token is not None
        return self._access_token

    async def _fetch_token(self) -> None:
        """Fetch a new access token."""
        try:
            async with self._session.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._uaid,
                    "client_secret": self._secret_key,
                },
            ) as resp:
                if resp.status in (401, 403):
                    raise YoLinkAuthFailError("Invalid UAC credentials")
                if resp.status != 200:
                    raise YoLinkClientError(
                        f"Token request failed with status {resp.status}"
                    )

                result = await resp.json()
                if "access_token" not in result:
                    raise YoLinkAuthFailError("No access_token in response")

                self._access_token = result["access_token"]
                # Calculate expiry: use expires_in from response, default to 2 hours
                expires_in = result.get("expires_in", 7200)
                self._token_expiry = time.time() + expires_in
                _LOGGER.debug("Fetched UAC access token, expires in %s seconds", expires_in)
        except ClientError as err:
            raise YoLinkClientError(f"Failed to fetch token: {err}") from err
