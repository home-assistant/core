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

from .const import (
    CONF_HIGH_PRECISION,
    CONF_LOCATION_IDX,
    DEFAULT_HIGH_PRECISION,
    DEFAULT_LOCATION_IDX,
    DOMAIN,
    SCAN_INTERVAL_DEFAULT,
    SCAN_INTERVAL_MINIMUM,
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

STEP_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT): vol.All(
            cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)
        )
    }
)

STEP_PRECISION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HIGH_PRECISION, default=DEFAULT_HIGH_PRECISION): bool,
    }
)

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


class EvoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Evohome."""

    # VERSION = 1
    # MINOR_VERSION = 1

    _token_manager: TokenManager
    _client: ec2.EvohomeClient

    def __init__(self) -> None:
        """Initialize a config flow handler for Evohome."""

        self._config: dict[str, Any] = {}
        self._option: dict[str, Any] = {}

    async def async_step_import(
        self, config_import: EvoConfigFileDictT
    ) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""

        # before testing the credentials (i.e. for load/save callbacks)
        self._config.update(
            {k: v for k, v in config_import.items() if k != CONF_SCAN_INTERVAL}
        )

        # first, check credentials, which will _abort_if_unique_id_configured()
        self._token_manager = await self._test_credentials(
            config_import[CONF_USERNAME], config_import[CONF_PASSWORD]
        )

        self._client = await self._test_location_idx(
            self._token_manager,
            config_import[CONF_LOCATION_IDX],
        )

        # a timedelta is not serializable, so convert to seconds
        self._option[CONF_SCAN_INTERVAL] = config_import[CONF_SCAN_INTERVAL].seconds

        # previously, high_precision were implicitly enabled, so enable for imports
        self._option[CONF_HIGH_PRECISION] = True

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

            except ec2.BadUserCredentialsError:
                errors["base"] = "invalid_auth"

            except ec2.ApiRequestFailedError:
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
                return self.async_create_entry(title="Evohome", data=self._config)

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
        self._abort_if_unique_id_configured()

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

    # VERSION = 1
    # MINOR_VERSION = 1

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize an options flow handler for Evohome."""

        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the first step of options flow."""
        return await self.async_step_scan_interval(user_input)

    async def async_step_scan_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the scan_interval option."""

        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_high_precision()

        return self.async_show_form(
            step_id="scan_interval", data_schema=STEP_INTERVAL_SCHEMA
        )

    async def async_step_high_precision(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Second page."""

        if user_input is not None:
            self.options.update(user_input)
            # Finished collecting all settings
            return self.async_create_entry(title="Evohome", data=self.options)

        return self.async_show_form(
            step_id="high_precision", data_schema=STEP_PRECISION_SCHEMA
        )
