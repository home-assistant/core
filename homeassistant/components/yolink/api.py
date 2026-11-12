"""API for yolink."""

import asyncio
from http import HTTPStatus
import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from yolink.auth_mgr import YoLinkAuthMgr
from yolink.const import OAUTH2_TOKEN
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)

_TOKEN_RETRY_DELAY = 60
# Leaves room for the device request in the coordinator's 10 second update.
_TOKEN_REQUEST_TIMEOUT = 5


def _parse_token_response(payload: Any) -> dict[str, Any]:
    """Return the token of a successful token response, or raise."""
    if not isinstance(payload, dict):
        raise YoLinkClientError("invalid_response", "Token response is not an object")

    # Refused credentials are reported with HTTP 200 and an error state.
    if payload.get("state") == "error":
        raise YoLinkAuthFailError("error", payload.get("msg", "unknown error"))

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise YoLinkClientError(
            "invalid_response", "Token response has no usable access token"
        )

    expires_in = payload.get("expires_in")
    if not isinstance(expires_in, int | float) or expires_in <= 0:
        raise YoLinkClientError(
            "invalid_response",
            f"Token response has an invalid lifetime: {expires_in!r}",
        )

    return payload


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


class StaticTokenAuth(YoLinkAuthMgr):
    """Provide yolink authentication with an already resolved access token."""

    def __init__(self, websession: ClientSession, access_token: str) -> None:
        """Initialize yolink static token Auth."""
        super().__init__(websession)
        self._access_token = access_token

    def access_token(self) -> str:
        """Return the access token."""
        return self._access_token

    async def check_and_refresh_token(self) -> str:
        """Return the access token, which cannot be refreshed."""
        return self._access_token


# Not a YoLinkLocalAuthMgr: the library's MQTT client would use local hub credentials.
class UACAuth(YoLinkAuthMgr):
    """Provide yolink authentication using User Access Credentials."""

    def __init__(
        self,
        websession: ClientSession,
        uaid: str,
        secret_key: str,
    ) -> None:
        """Initialize yolink UAC Auth."""
        super().__init__(websession)
        self._client_id = uaid
        self._client_secret = secret_key
        self._token: dict[str, Any] | None = None
        self._token_lock = asyncio.Lock()

    def access_token(self) -> str | None:
        """Return the access token."""
        if self._token is None:
            return None
        return self._token["access_token"]

    async def check_and_refresh_token(self) -> str:
        """Check and refresh the token if needed."""
        async with self._token_lock:
            cached = self._token
            if cached is not None and time.time() < cached["refresh_at"]:
                return cached["access_token"]
            try:
                token = await self._token_request()
            except YoLinkAuthFailError:
                # The credentials were refused, retrying cannot fix that.
                raise
            except YoLinkClientError as err:
                # A cached token outlives a transient failure of the token endpoint.
                if cached is None or time.time() >= cached["expires_at"]:
                    raise
                cached["refresh_at"] = min(
                    time.time() + _TOKEN_RETRY_DELAY, cached["expires_at"]
                )
                _LOGGER.debug(
                    "UAC token refresh failed, keeping the cached token: %s",
                    err.message,
                )
                return cached["access_token"]
            now = time.time()
            # Refresh at half the lifetime to leave room to retry a failing endpoint.
            token["refresh_at"] = now + token["expires_in"] / 2
            token["expires_at"] = now + token["expires_in"]
            self._token = token
            return token["access_token"]

    async def _token_request(self) -> dict[str, Any]:
        """Request a new access token from the yolink token endpoint."""
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
                timeout=ClientTimeout(total=_TOKEN_REQUEST_TIMEOUT),
            ) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    try:
                        error_response = await resp.json()
                    except ClientError, ValueError:
                        error_response = None
                    if not isinstance(error_response, dict):
                        error_response = {}
                    error_code = error_response.get("error", "unknown")
                    error_desc = error_response.get(
                        "error_description", f"HTTP {resp.status}"
                    )
                    _LOGGER.debug(
                        "UAC token request failed (%s): %s", error_code, error_desc
                    )
                    if resp.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                        raise YoLinkAuthFailError(error_code, error_desc)
                    raise YoLinkClientError(error_code, error_desc)
                try:
                    payload = await resp.json()
                except (ClientError, ValueError) as err:
                    raise YoLinkClientError(
                        "invalid_response", "Token response is not valid JSON"
                    ) from err
        except (ClientError, OSError) as err:
            _LOGGER.debug("UAC token request failed: %s", err)
            raise YoLinkClientError("request_failed", str(err)) from err

        return _parse_token_response(payload)
