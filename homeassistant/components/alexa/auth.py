"""Support for Alexa skill auth."""

import json
import logging
from datetime import datetime, timedelta

import requests

from .const import DATE_FORMAT

_LOGGER = logging.getLogger(__name__)

LWA_TOKEN_URI = "https://api.amazon.com/auth/o2/token"
LWA_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
}

PREEMPTIVE_REFRESH_TTL_IN_SECONDS = 300
STORAGE_KEY = 'alexa_auth'
STORAGE_VERSION = 1
STORAGE_EXPIRE_TIME = "expire_time"
STORAGE_ACCESS_TOKEN = "access_token"
STORAGE_REFRESH_TOKEN = "refresh_token"


class Auth:
    """Handle authentication to send events to Alexa"""

    def __init__(self, hass, client_id, client_secret):
        self.hass = hass

        self.client_id = client_id
        self.client_secret = client_secret

        self._prefs = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    async def async_do_auth(self, accept_grant_code):
        # access token not retrieved yet for the first time, so this should
        # be an access token request

        lwa_params = {
            "grant_type": "authorization_code",
            "code": accept_grant_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        _LOGGER.debug("Calling LWA to get the access token (first time), "
                      "with: {0}".format(json.dumps(lwa_params)))

        return await self._async_request_new_token(lwa_params)

    async def async_is_auth_done(self):
        if self._prefs is None:
            await self.async_load_preferences()

        return self._prefs[STORAGE_ACCESS_TOKEN] is not None

    async def async_get_access_token(self):
        """Performs access token or token refresh request as needed and returns
        valid access token """

        if self._prefs is None:
            await self.async_load_preferences()

        if self.is_token_valid():
            _LOGGER.debug("Token still valid, using it.")
            return self._prefs[STORAGE_ACCESS_TOKEN]

        if self._prefs[STORAGE_REFRESH_TOKEN] is None:
            _LOGGER.error("Token invalid and no refresh token available.")

        lwa_params = {
            "grant_type": "refresh_token",
            "refresh_token": self._prefs[STORAGE_REFRESH_TOKEN],
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        _LOGGER.debug("Calling LWA to refresh the access token.")
        return await self._async_request_new_token(lwa_params)

    def is_token_valid(self):
        """Checks if a token is already loaded and if it is still valid"""

        if not self._prefs[STORAGE_ACCESS_TOKEN]:
            return False

        expire_time = datetime.strptime(self._prefs[STORAGE_EXPIRE_TIME],
                                        DATE_FORMAT)
        preemptive_expire_time = expire_time - timedelta(
            seconds=PREEMPTIVE_REFRESH_TTL_IN_SECONDS)

        if datetime.utcnow() > preemptive_expire_time:
            return False

        return True

    async def _async_request_new_token(self, lwa_params):
        # TODO: use aiohttp
        response = requests.post(LWA_TOKEN_URI, headers=LWA_HEADERS,
                                 data=lwa_params, allow_redirects=True)
        _LOGGER.debug(
            "LWA response header: {0}".format(format(response.headers)))
        _LOGGER.debug(
            "LWA response status: {0}".format(
                format(response.status_code)))
        _LOGGER.debug(
            "LWA response body  : {0}".format(format(response.text)))

        if response.status_code != 200:
            _LOGGER.error("Error calling LWA to get auth token.")
            return None

        access_token = json.loads(response.text)["access_token"]
        refresh_token = json.loads(response.text)["refresh_token"]
        expires_in = json.loads(response.text)["expires_in"]
        expire_time = datetime.utcnow() + timedelta(seconds=expires_in)

        await self._async_update_preferences(access_token, refresh_token,
                                             expire_time.strftime(DATE_FORMAT))

        return access_token

    async def async_load_preferences(self):
        """Load preferences with stored tokens."""
        self._prefs = await self._store.async_load()

        if self._prefs is None:
            self._prefs = {
                STORAGE_ACCESS_TOKEN: None,
                STORAGE_REFRESH_TOKEN: None,
                STORAGE_EXPIRE_TIME: None
            }

    async def _async_update_preferences(self, access_token, refresh_token,
                                        expire_time):
        """Update user preferences."""
        if access_token is not None:
            self._prefs[STORAGE_ACCESS_TOKEN] = access_token
        if refresh_token is not None:
            self._prefs[STORAGE_REFRESH_TOKEN] = refresh_token
        if expire_time is not None:
            self._prefs[STORAGE_EXPIRE_TIME] = expire_time
        await self._store.async_save(self._prefs)
