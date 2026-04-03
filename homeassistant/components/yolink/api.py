"""API for yolink."""

from __future__ import annotations

import asyncio
import logging
import time

from aiohttp import ClientError, ClientSession, ClientTimeout
from yolink.auth_mgr import YoLinkAuthMgr
from yolink.const import OAUTH2_TOKEN
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

_LOGGER = logging.getLogger(__name__)

# Refresh token 20 seconds before expiry to account for clock skew
CLOCK_OUT_OF_SYNC_MAX_SEC = 20


class ConfigEntryAuth(YoLinkAuthMgr):
    """Provide yolink authentication tied to an OAuth2 based config entry.

    Token refresh is handled by Home Assistant's OAuth2Session.
    access_token() must be a method (not property) because the library
    calls it as self.access_token() in http_auth_header().
    """

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize yolink Auth."""
        super().__init__(websession)
        self.hass = hass
        self._oauth_session = oauth_session

    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._oauth_session.token.get("access_token")

    async def check_and_refresh_token(self) -> str:
        """Check and refresh the token if needed."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]


class UACAuth(YoLinkAuthMgr):
    """Provide yolink authentication using UAC credentials.

    Extends YoLinkAuthMgr (not YoLinkLocalAuthMgr) because the library's
    MQTT client uses isinstance(auth_mgr, YoLinkLocalAuthMgr) to switch
    between local-hub and cloud MQTT credential formats. UAC uses the cloud
    broker, so we must not be an instance of YoLinkLocalAuthMgr.

    Token lifecycle (fetch, expiry, locking) is modeled after
    YoLinkLocalAuthMgr but implemented here to avoid the isinstance issue.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        uaid: str,
        secret_key: str,
    ) -> None:
        """Initialize yolink UAC Auth."""
        super().__init__(websession)
        self.hass = hass
        self._client_id = uaid
        self._client_secret = secret_key
        self._token: dict | None = None
        self._token_lock = asyncio.Lock()

    def access_token(self) -> str | None:
        """Return the current access token."""
        if self._token is None:
            return None
        return self._token["access_token"]

    @property
    def _token_valid(self) -> bool:
        """Check if the current token is still valid."""
        if self._token is None:
            return False
        return self._token["expires_at"] > time.time() + CLOCK_OUT_OF_SYNC_MAX_SEC

    async def check_and_refresh_token(self) -> str:
        """Check and refresh the token if needed."""
        async with self._token_lock:
            if self._token_valid and self._token is not None:
                return self._token["access_token"]
            new_token = await self._token_request()
            new_token["expires_at"] = time.time() + new_token["expires_in"]
            self._token = new_token
            return self._token["access_token"]

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return await self.check_and_refresh_token()

    async def _token_request(self) -> dict:
        """Fetch a new access token from the YoLink OAuth2 endpoint."""
        try:
            async with self._session.post(
                url=OAUTH2_TOKEN,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "scope": "create",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    try:
                        error_response = await resp.json()
                    except ClientError, ValueError:
                        error_response = {}
                    error_code = error_response.get("error", "unknown")
                    error_desc = error_response.get(
                        "error_description", f"HTTP {resp.status}"
                    )
                    _LOGGER.error(
                        "UAC token request failed (%s): %s", error_code, error_desc
                    )
                    if resp.status in (401, 403):
                        raise YoLinkAuthFailError(error_code, error_desc)
                    raise YoLinkClientError(error_code, error_desc)
                result = await resp.json()
                # Token endpoint may return HTTP 200 with error in the body
                if "access_token" not in result:
                    error_code = result.get("code", result.get("error", "unknown"))
                    error_desc = result.get(
                        "desc",
                        result.get("error_description", "Authentication failed"),
                    )
                    raise YoLinkAuthFailError(error_code, error_desc)
                return result
        except (ClientError, OSError) as err:
            _LOGGER.error("UAC token request failed: %s", err)
            raise YoLinkClientError("request_failed", str(err)) from err
