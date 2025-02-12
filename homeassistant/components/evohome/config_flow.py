"""Config flow for the Evohome integration."""

from __future__ import annotations

from typing import Any

import evohomeasync2 as ec2
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_LOCATION_IDX,
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

STEP_SCAN_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT): vol.All(
            cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)
        )
    }
)


class EvohomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for evohome."""

    VERSION = 1

    _token_manager: TokenManager
    _location_idx: int

    def __init__(self) -> None:
        """Initialize the flow."""
        self._config: dict[str, Any] = {}

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""

        import_config[CONF_LOCATION_IDX] = import_config.get(CONF_LOCATION_IDX, 0)
        import_config[CONF_SCAN_INTERVAL] = import_config.get(
            CONF_SCAN_INTERVAL, SCAN_INTERVAL_MINIMUM
        )

        self._token_manager = await self._test_credentials(**import_config)
        self._location_idx = await self._test_location_idx(**import_config)

        self._config.update(import_config)
        return self.async_create_entry(title="Evohome", data=self._config)

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the initial step (username/password)."""

        if user_input is not None:
            # Validate credentials, test connection, etc.
            # If there's an error, show the form with errors
            # e.g., raise an exception or return self.async_show_form(...)
            self._token_manager = await self._test_credentials(**user_input)

            self._config.update(user_input)
            return await self.async_step_location()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

    async def async_step_location(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the second step (location index)."""

        if user_input is not None:
            # Validate location as needed
            await self._test_location_idx(**user_input)

            self._config.update(user_input)
            return await self.async_step_scan_interval()

        return self.async_show_form(
            step_id="location", data_schema=STEP_LOCATION_SCHEMA
        )

    async def async_step_scan_interval(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the final step (scan interval)."""

        if user_input is not None:
            # Validate the scan interval as needed
            self._config.update(user_input)
            return self.async_create_entry(title="Evohome", data=self._config)

        return self.async_show_form(
            step_id="scan_interval", data_schema=STEP_SCAN_INTERVAL_SCHEMA
        )

    async def _test_credentials(
        self, /, username: str, password: str, **kwargs: Any
    ) -> TokenManager:
        """Test whether provided credentials are valid."""

        token_manager = TokenManager(
            self.hass,
            username,
            password,
            async_get_clientsession(self.hass),
        )

        # fetch a new access token, using the credentials, not any refresh_token
        assert not token_manager._refresh_token  # noqa: SLF001

        await token_manager.fetch_access_token()  # ? raise ec2.BadUserCredentialsError:

        return token_manager

    async def _test_location_idx(self, /, location_idx: int, **kwargs: Any) -> int:
        """Test whether provided credentials are valid."""

        assert self._token_manager is not None  # mypy

        client = ec2.EvohomeClient(self._token_manager)

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

        return location_idx
