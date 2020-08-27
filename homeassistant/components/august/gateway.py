"""Handle August connection setup and authentication."""

import asyncio
import logging

from aiohttp import ClientError
from august.api_async import ApiAsync
from august.authenticator_async import AuthenticationState, AuthenticatorAsync

from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DEFAULT_AUGUST_CONFIG_FILE,
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
        self._api = None
        self._authenticator = None
        self._authentication = None

    @property
    def authenticator(self):
        """August authentication object from py-august."""
        return self._authenticator

    @property
    def authentication(self):
        """August authentication object from py-august."""
        return self._authentication

    @property
    def access_token(self):
        """Access token for the api."""
        return self._authentication.access_token

    @property
    def api(self):
        """August api object from py-august."""
        return self._api

    def config_entry(self):
        """Config entry."""
        return {
            CONF_LOGIN_METHOD: self._config[CONF_LOGIN_METHOD],
            CONF_USERNAME: self._config[CONF_USERNAME],
            CONF_PASSWORD: self._config[CONF_PASSWORD],
            CONF_INSTALL_ID: self._config.get(CONF_INSTALL_ID),
            CONF_TIMEOUT: self._config.get(CONF_TIMEOUT),
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

        self._api = ApiAsync(
            self._aiohttp_session, timeout=self._config.get(CONF_TIMEOUT)
        )

        self._authenticator = AuthenticatorAsync(
            self._api,
            self._config[CONF_LOGIN_METHOD],
            self._config[CONF_USERNAME],
            self._config[CONF_PASSWORD],
            install_id=self._config.get(CONF_INSTALL_ID),
            access_token_cache_file=self._hass.config.path(
                self._access_token_cache_file
            ),
        )

        await self._authenticator.async_setup_authentication()

    async def async_authenticate(self):
        """Authenticate with the details provided to setup."""
        self._authentication = None
        try:
            self._authentication = await self.authenticator.async_authenticate()
        except ClientError as ex:
            _LOGGER.error("Unable to connect to August service: %s", str(ex))
            raise CannotConnect

        if self._authentication.state == AuthenticationState.BAD_PASSWORD:
            raise InvalidAuth

        if self._authentication.state == AuthenticationState.REQUIRES_VALIDATION:
            raise RequireValidation

        if self._authentication.state != AuthenticationState.AUTHENTICATED:
            _LOGGER.error(
                "Unknown authentication state: %s", self._authentication.state
            )
            raise InvalidAuth

        return self._authentication

    async def async_refresh_access_token_if_needed(self):
        """Refresh the august access token if needed."""
        if self.authenticator.should_refresh():
            async with self._token_refresh_lock:
                refreshed_authentication = (
                    await self.authenticator.async_refresh_access_token(force=False)
                )
                _LOGGER.info(
                    "Refreshed august access token. The old token expired at %s, and the new token expires at %s",
                    self.authentication.access_token_expires,
                    refreshed_authentication.access_token_expires,
                )
                self._authentication = refreshed_authentication
