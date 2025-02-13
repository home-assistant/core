"""Config flow for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, NotRequired, TypedDict

import evohomeasync2 as ec2
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed  # , ConfigEntryNotReady
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
from .storage import TokenManager

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


class EvoConfigFileDictT(TypedDict):
    """The Evohome configuration.yaml data (under evohome:)."""

    username: str
    password: str
    location_idx: NotRequired[int]
    scan_interval: NotRequired[timedelta]


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

        # the configuration file CONFIG_SCHEMA required username and password,
        # but location_idx and scan_interval were optional

        config_import[CONF_LOCATION_IDX] = config_import.get(
            CONF_LOCATION_IDX, DEFAULT_LOCATION_IDX
        )

        # high_precision must now be explicitly enabled
        self._option[CONF_HIGH_PRECISION] = DEFAULT_HIGH_PRECISION
        self._option[CONF_SCAN_INTERVAL] = config_import.pop(
            CONF_SCAN_INTERVAL, SCAN_INTERVAL_DEFAULT
        )

        self._token_manager = await self._test_credentials(
            self.hass, config_import[CONF_USERNAME], config_import[CONF_PASSWORD]
        )
        self._client = await self._test_location_idx(
            self._token_manager,
            config_import[CONF_LOCATION_IDX],
        )

        self._config.update(config_import)

        return self.async_create_entry(
            title="Evohome", data=self._config, options=self._option
        )

    async def async_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth step (username/password) when BadUserCredentials raised."""

        if user_input is not None:
            self._token_manager = await self._test_credentials(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

            self._config.update(user_input)
            return self.async_create_entry(title="Evohome", data=self._config)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (username/password)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._token_manager = await self._test_credentials(
                    self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
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

    @staticmethod
    async def _test_credentials(
        hass: HomeAssistant, username: str, password: str
    ) -> TokenManager:
        """Validate the user credentials (that authentication is successful)."""

        token_manager = TokenManager(
            hass,
            username,
            password,
            async_get_clientsession(hass),
        )

        # fetch a new access token from the vendor (i.e. not from the cache)
        assert not token_manager.refresh_token
        try:
            await (
                token_manager.fetch_access_token()
            )  # ? raise ec2.BadUserCredentialsError:
        except ec2.BadUserCredentialsError as err:
            raise ConfigEntryAuthFailed(err) from err
        return token_manager

    @staticmethod
    async def _test_location_idx(
        token_manager: TokenManager, location_idx: int
    ) -> ec2.EvohomeClient:
        """Validate the location_idx (that the location exists)."""

        client = ec2.EvohomeClient(token_manager)

        await client.update(dont_update_status=True)  # ? raise ec2.EvohomeError:

        try:
            client.locations[location_idx]
        except IndexError as err:
            raise IndexError(
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
