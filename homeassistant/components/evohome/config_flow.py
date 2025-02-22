"""Config flow for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final, NotRequired, TypedDict

import evohomeasync2 as ec2
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    CONF_HIGH_PRECISION,
    CONF_LOCATION_IDX,
    DEFAULT_HIGH_PRECISION,
    DEFAULT_HIGH_PRECISION_LEGACY,
    DEFAULT_LOCATION_IDX,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MINIMUM_SCAN_INTERVAL,
    MINIMUM_SCAN_INTERVAL_LEGACY,
    STORAGE_KEY,
    STORAGE_VER,
)
from .storage import TokenDataT, TokenManager

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,  # an email address
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_LOCATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCATION_IDX, default=DEFAULT_LOCATION_IDX): vol.Coerce(int),
    }
)

DEFAULT_OPTIONS: Final = {
    CONF_HIGH_PRECISION: DEFAULT_HIGH_PRECISION,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}

SZ_TOKEN_DATA: Final = "token_data"


_LOGGER = logging.getLogger(__name__.rsplit(".", 1)[0])


class EvoConfigFileDictT(TypedDict):
    """The Evohome configuration.yaml data (under evohome:)."""

    username: str
    password: str
    location_idx: int
    scan_interval: timedelta


class EvoRuntimeDataT(TypedDict):
    """The Evohome runtime data."""

    coordinator: str
    password: str
    token_manager: NotRequired[int]


class _TokenStoreT(TypedDict):
    username: str
    refresh_token: str
    access_token: str
    access_token_expires: str  # dt.isoformat()  # TZ-aware
    session_id: NotRequired[str]
    session_id_expires: NotRequired[str]  # dt.isoformat()  # TZ-aware


class EvoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Evohome."""

    _token_manager: TokenManager
    _client: ec2.EvohomeClient

    def __init__(self) -> None:
        """Initialize a config flow handler for Evohome."""

        self._config: dict[str, Any] = {}
        self._option: dict[str, Any] = DEFAULT_OPTIONS

    async def async_step_import(self, config: EvoConfigFileDictT) -> ConfigFlowResult:
        """Handle a flow initiated by import from a configuration file.

        Will abort if the unique_id (username) is already configured.
        """

        # for import, do not validate the user credentials/location index here
        await self.async_set_unique_id(config[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()  # is this required?

        self._config = {k: v for k, v in config.items() if k != CONF_SCAN_INTERVAL}

        # leverage any cached tokens by moving them to the config entry
        store: Store[_TokenStoreT] = Store(self.hass, STORAGE_VER, STORAGE_KEY)
        cache: _TokenStoreT | None = await store.async_load()

        await store.async_remove()

        if cache is not None and cache.get(CONF_USERNAME) == config[CONF_USERNAME]:
            self._config[SZ_TOKEN_DATA] = cache

        # a timedelta is not serializable, so convert to seconds
        self._option[CONF_SCAN_INTERVAL] = config[CONF_SCAN_INTERVAL].seconds

        # before config flow, high_precision was implicitly enabled
        self._option[CONF_HIGH_PRECISION] = DEFAULT_HIGH_PRECISION_LEGACY

        return self.async_create_entry(
            title="Evohome", data=self._config, options=self._option
        )

    async def async_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth step (username/password) when BadUserCredentials raised."""

        errors: dict[str, str] = {}

        if user_input is not None:
            # before testing the credentials (i.e. for load/save callbacks)
            self._config.update(user_input)

            self._token_manager = await self._test_credentials(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

            return self.async_create_entry(title="Evohome", data=self._config)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (username/password)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            # before testing the credentials (i.e. for load/save callbacks)
            self._config.update(user_input)

            try:
                self._token_manager = await self._test_credentials(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )

            except ConfigEntryAuthFailed:  # ec2.BadUserCredentialsError
                errors["base"] = "invalid_auth"

            except ConfigEntryNotReady:  # ec2.ApiRequestFailedError:
                errors["base"] = "cannot_connect"

            else:
                self._config.update(user_input)
                return await self.async_step_location()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the second/final step (location index)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._client = await self._test_location_idx(
                    self._token_manager, user_input[CONF_LOCATION_IDX]
                )

            except (IndexError, ec2.ApiRequestFailedError):
                errors["base"] = "cannot_connect"

            else:
                self._config.update(user_input)
                return self.async_create_entry(
                    title="Evohome", data=self._config, options=self._option
                )

        return self.async_show_form(
            step_id="location", data_schema=STEP_LOCATION_SCHEMA, errors=errors
        )

    async def _test_credentials(self, username: str, password: str) -> TokenManager:
        """Validate the user credentials (that authentication is successful)."""

        token_manager = TokenManager(
            username,
            password,
            async_get_clientsession(self.hass),
            cache_loader=self._load_token_data,
            cache_saver=self._save_token_data,
            logger=_LOGGER,
        )

        # fetch a new access token from the vendor (i.e. not from the cache)
        assert not token_manager.refresh_token

        try:
            await token_manager.get_access_token()

        except ec2.BadUserCredentialsError as err:
            raise ConfigEntryAuthFailed(str(err)) from err

        except ec2.AuthenticationFailedError as err:
            raise ConfigEntryNotReady(str(err)) from err

        await self.async_set_unique_id(username.lower())
        self._abort_if_unique_id_configured()  # is this required?

        return token_manager

    async def _test_location_idx(
        self, token_manager: TokenManager, location_idx: int
    ) -> ec2.EvohomeClient:
        """Validate the location_idx (that the location exists)."""

        client = ec2.EvohomeClient(token_manager)

        try:
            await client.update(dont_update_status=True)  # ? raise ec2.EvohomeError:

        except ec2.ApiRequestFailedError as err:
            raise ConfigEntryNotReady(str(err)) from err

        try:
            client.locations[location_idx]

        except IndexError as err:
            raise ConfigEntryAuthFailed(
                f"""
                    Config error: 'location_idx' = {location_idx},
                    but the valid range is 0-{len(client.locations) - 1}.
                    Unable to continue. Fix any configuration errors and restart HA
                """
            ) from err

        return client

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EvoOptionsFlowHandler:
        """Define the options flow for Evohome."""
        return EvoOptionsFlowHandler(config_entry)

    async def _load_token_data(self, client_id: str) -> TokenDataT | None:
        """Return token data as from an empty cache."""
        return None  # will force user credentials to be validated

    async def _save_token_data(self, client_id: str, token_data: TokenDataT) -> None:
        """Save the token data to the config entry, so it can be used later."""

        if client_id == self._config[CONF_USERNAME]:
            self._config[SZ_TOKEN_DATA] = token_data


class EvoOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Evohome."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize an options flow handler for Evohome."""

        self._options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the first step of options flow.

        Provides responsible default values for high_precision and scan_interval.
        """

        errors: dict[str, str] = {}

        self._options = dict(self.config_entry.options)

        if user_input is not None:
            self._options.update(user_input)
            # Finished collecting all settings
            return self.async_create_entry(title="Evohome", data=self._options)

        # suggest False, rather than previous value: self._options[CONF_HIGH_PRECISION]
        default_high_precision = DEFAULT_HIGH_PRECISION

        # suggest 180 (not 60) seconds, unless previously set to a higher value
        default_scan_interval = max(
            (MINIMUM_SCAN_INTERVAL, self._options[CONF_SCAN_INTERVAL])
        )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_HIGH_PRECISION, default=default_high_precision): bool,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=default_scan_interval
                ): vol.All(
                    cv.positive_int, vol.Range(min=MINIMUM_SCAN_INTERVAL_LEGACY)
                ),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
