"""Handle August connection setup and authentication."""

import asyncio
import logging
import os

from aiohttp import ClientError, ClientResponseError
from yalexs.api_async import ApiAsync
from yalexs.authenticator_async import AuthenticationState, AuthenticatorAsync

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    HTTP_UNAUTHORIZED,
)
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DEFAULT_AUGUST_CONFIG_FILE,
    DEFAULT_TIMEOUT,
    VERIFICATION_CODE_KEY,
)
from .exceptions import CannotConnect, InvalidAuth, RequireValidation

_LOGGER = logging.getLogger(__name__)


class AugustGateway:
    """Handle the connection to August."""

    def __init__(self, hass):
        """Init the connection."""
        self._aiohttp_session = aiohttp_client.async_get_clientsession(hass)
        self._token_refresh_lock = asyncio.Lock()
        self._access_token_cache_file = None
        self._hass = hass
        self._config = None
        self.api = None
        self.authenticator = None
        self.authentication = None

    @property
    def access_token(self):
        """Access token for the api."""
        return self.authentication.access_token

    def config_entry(self):
        """Config entry."""
        return {
            CONF_LOGIN_METHOD: self._config[CONF_LOGIN_METHOD],
            CONF_USERNAME: self._config[CONF_USERNAME],
            CONF_INSTALL_ID: self._config.get(CONF_INSTALL_ID),
            CONF_ACCESS_TOKEN_CACHE_FILE: self._access_token_cache_file,
        }

    async def async_setup(self, conf):
        """Create the api and authenticator objects."""
        if conf.get(VERIFICATION_CODE_KEY):
            return

        self._access_token_cache_file = conf.get(
            CONF_ACCESS_TOKEN_CACHE_FILE,
            f".{conf[CONF_USERNAME]}{DEFAULT_AUGUST_CONFIG_FILE}",
        )
        self._config = conf

        self.api = ApiAsync(
            self._aiohttp_session,
            timeout=self._config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )

        self.authenticator = AuthenticatorAsync(
            self.api,
            self._config[CONF_LOGIN_METHOD],
            self._config[CONF_USERNAME],
            self._config.get(CONF_PASSWORD, ""),
            install_id=self._config.get(CONF_INSTALL_ID),
            access_token_cache_file=self._hass.config.path(
                self._access_token_cache_file
            ),
        )

        await self.authenticator.async_setup_authentication()

    async def async_authenticate(self):
        """Authenticate with the details provided to setup."""
        self.authentication = None
        try:
            self.authentication = await self.authenticator.async_authenticate()
            if self.authentication.state == AuthenticationState.AUTHENTICATED:
                # Call the locks api to verify we are actually
                # authenticated because we can be authenticated
                # by have no access
                await self.api.async_get_operable_locks(self.access_token)
        except ClientResponseError as ex:
            if ex.status == HTTP_UNAUTHORIZED:
                raise InvalidAuth from ex

            raise CannotConnect from ex
        except ClientError as ex:
            _LOGGER.error("Unable to connect to August service: %s", str(ex))
            raise CannotConnect from ex

        if self.authentication.state == AuthenticationState.BAD_PASSWORD:
            raise InvalidAuth

        if self.authentication.state == AuthenticationState.REQUIRES_VALIDATION:
            raise RequireValidation

        if self.authentication.state != AuthenticationState.AUTHENTICATED:
            _LOGGER.error("Unknown authentication state: %s", self.authentication.state)
            raise InvalidAuth

        return self.authentication

    async def async_reset_authentication(self):
        """Remove the cache file."""
        await self._hass.async_add_executor_job(self._reset_authentication)

    def _reset_authentication(self):
        """Remove the cache file."""
        if os.path.exists(self._access_token_cache_file):
            os.unlink(self._access_token_cache_file)

    async def async_refresh_access_token_if_needed(self):
        """Refresh the august access token if needed."""
        if not self.authenticator.should_refresh():
            return
        async with self._token_refresh_lock:
            refreshed_authentication = (
                await self.authenticator.async_refresh_access_token(force=False)
            )
            _LOGGER.info(
                "Refreshed august access token. The old token expired at %s, and the new token expires at %s",
                self.authentication.access_token_expires,
                refreshed_authentication.access_token_expires,
            )
            self.authentication = refreshed_authentication
