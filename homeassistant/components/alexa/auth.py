"""Support for Alexa skill auth."""
import asyncio
from asyncio import timeout
from datetime import datetime, timedelta
from http import HTTPStatus
import json
import logging
from typing import Any

import aiohttp

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import STORAGE_ACCESS_TOKEN, STORAGE_REFRESH_TOKEN
from .diagnostics import async_redact_lwa_params

_LOGGER = logging.getLogger(__name__)

LWA_TOKEN_URI = "https://api.amazon.com/auth/o2/token"
LWA_HEADERS = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}

PREEMPTIVE_REFRESH_TTL_IN_SECONDS = 300
STORAGE_KEY = "alexa_auth"
STORAGE_VERSION = 1
STORAGE_EXPIRE_TIME = "expire_time"


class Auth:
    """Handle authentication to send events to Alexa."""

    def __init__(self, hass: HomeAssistant, client_id: str, client_secret: str) -> None:
        """Initialize the Auth class."""
        self.hass = hass

        self.client_id = client_id
        self.client_secret = client_secret

        self._prefs: dict[str, Any] | None = None
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

        self._get_token_lock = asyncio.Lock()

    async def async_do_auth(self, accept_grant_code: str) -> str | None:
        """Do authentication with an AcceptGrant code."""
        # access token not retrieved yet for the first time, so this should
        # be an access token request

        lwa_params: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": accept_grant_code,
            CONF_CLIENT_ID: self.client_id,
            CONF_CLIENT_SECRET: self.client_secret,
        }
        _LOGGER.debug(
            "Calling LWA to get the access token (first time), with: %s",
            json.dumps(async_redact_lwa_params(lwa_params)),
        )

        return await self._async_request_new_token(lwa_params)

    @callback
    def async_invalidate_access_token(self) -> None:
        """Invalidate access token."""
        assert self._prefs is not None
        self._prefs[STORAGE_ACCESS_TOKEN] = None

    async def async_get_access_token(self) -> str | None:
        """Perform access token or token refresh request."""
        async with self._get_token_lock:
            if self._prefs is None:
                await self.async_load_preferences()

            assert self._prefs is not None
            if self.is_token_valid():
                _LOGGER.debug("Token still valid, using it")
                token: str = self._prefs[STORAGE_ACCESS_TOKEN]
                return token

            if self._prefs[STORAGE_REFRESH_TOKEN] is None:
                _LOGGER.debug("Token invalid and no refresh token available")
                return None

            lwa_params: dict[str, str] = {
                "grant_type": "refresh_token",
                "refresh_token": self._prefs[STORAGE_REFRESH_TOKEN],
                CONF_CLIENT_ID: self.client_id,
                CONF_CLIENT_SECRET: self.client_secret,
            }

            _LOGGER.debug("Calling LWA to refresh the access token")
            return await self._async_request_new_token(lwa_params)

    @callback
    def is_token_valid(self) -> bool:
        """Check if a token is already loaded and if it is still valid."""
        assert self._prefs is not None
        if not self._prefs[STORAGE_ACCESS_TOKEN]:
            return False

        expire_time: datetime | None = dt_util.parse_datetime(
            self._prefs[STORAGE_EXPIRE_TIME]
        )
        assert expire_time is not None
        preemptive_expire_time = expire_time - timedelta(
            seconds=PREEMPTIVE_REFRESH_TTL_IN_SECONDS
        )

        return dt_util.utcnow() < preemptive_expire_time

    async def _async_request_new_token(self, lwa_params: dict[str, str]) -> str | None:
        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            async with timeout(10):
                response = await session.post(
                    LWA_TOKEN_URI,
                    headers=LWA_HEADERS,
                    data=lwa_params,
                    allow_redirects=True,
                )

        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout calling LWA to get auth token")
            return None

        _LOGGER.debug("LWA response header: %s", response.headers)
        _LOGGER.debug("LWA response status: %s", response.status)

        if response.status != HTTPStatus.OK:
            _LOGGER.error("Error calling LWA to get auth token")
            return None

        response_json = await response.json()
        _LOGGER.debug("LWA response body  : %s", async_redact_lwa_params(response_json))

        access_token: str = response_json["access_token"]
        refresh_token: str = response_json["refresh_token"]
        expires_in: int = response_json["expires_in"]
        expire_time = dt_util.utcnow() + timedelta(seconds=expires_in)

        await self._async_update_preferences(
            access_token, refresh_token, expire_time.isoformat()
        )

        return access_token

    async def async_load_preferences(self) -> None:
        """Load preferences with stored tokens."""
        self._prefs = await self._store.async_load()

        if self._prefs is None:
            self._prefs = {
                STORAGE_ACCESS_TOKEN: None,
                STORAGE_REFRESH_TOKEN: None,
                STORAGE_EXPIRE_TIME: None,
            }

    async def _async_update_preferences(
        self, access_token: str, refresh_token: str, expire_time: str
    ) -> None:
        """Update user preferences."""
        if self._prefs is None:
            await self.async_load_preferences()
            assert self._prefs is not None

        if access_token is not None:
            self._prefs[STORAGE_ACCESS_TOKEN] = access_token
        if refresh_token is not None:
            self._prefs[STORAGE_REFRESH_TOKEN] = refresh_token
        if expire_time is not None:
            self._prefs[STORAGE_EXPIRE_TIME] = expire_time
        await self._store.async_save(self._prefs)
