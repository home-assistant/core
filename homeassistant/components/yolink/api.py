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
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

_LOGGER = logging.getLogger(__name__)

# Fields a token response carries when it reports an error instead of a token.
_TOKEN_ERROR_FIELDS = ("code", "desc", "error", "error_description")


def _parse_token_response(payload: Any) -> dict[str, Any]:
    """Return the token of a successful token response, or raise."""
    if not isinstance(payload, dict):
        raise YoLinkClientError("invalid_response", "Token response is not an object")

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        if not any(field in payload for field in _TOKEN_ERROR_FIELDS):
            # Nothing was refused, the response is simply unusable. Reporting it
            # as an authentication failure would ask the user to reauthenticate
            # over what the next request may well answer correctly.
            raise YoLinkClientError(
                "invalid_response", "Token response has no usable access token"
            )
        # Invalid credentials are reported with HTTP 200 and an error body.
        raise YoLinkAuthFailError(
            payload.get("code", payload.get("error", "unknown")),
            payload.get("desc", payload.get("error_description", "unknown error")),
        )

    expires_in = payload.get("expires_in")
    if (
        # A bool is an int, but not a lifetime.
        isinstance(expires_in, bool)
        or not isinstance(expires_in, int | float)
        or expires_in <= 0
    ):
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
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize yolink Auth."""
        super().__init__(websession)
        self.hass = hass
        self._oauth_session = oauth_session

    def access_token(self) -> str:
        """Return the access token."""
        return self._oauth_session.token["access_token"]

    async def check_and_refresh_token(self) -> str:
        """Check and refresh the token if needed."""
        await self._oauth_session.async_ensure_token_valid()
        return self.access_token()


class StaticTokenAuth(YoLinkAuthMgr):
    """Provide yolink authentication with an already obtained access token.

    Used by the config flow, where an OAuth2 token has been resolved but no
    config entry exists yet to refresh it from.
    """

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


class UACAuth(YoLinkAuthMgr):
    """Provide yolink authentication using User Access Credentials.

    Extends YoLinkAuthMgr instead of the library's YoLinkLocalAuthMgr because
    the library's MQTT client uses isinstance(auth_mgr, YoLinkLocalAuthMgr) to
    select local hub credentials, while UAC connects to the cloud broker.
    """

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
            if self._token is None or self._token["refresh_at"] <= time.time():
                token = await self._token_request()
                # Refresh once half the lifetime has passed, so a failing token
                # endpoint can be retried while the current token still works.
                token["refresh_at"] = time.time() + token["expires_in"] / 2
                self._token = token
            return self._token["access_token"]

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
                timeout=ClientTimeout(total=10),
            ) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    try:
                        error_response = await resp.json()
                    except ClientError, ValueError:
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
