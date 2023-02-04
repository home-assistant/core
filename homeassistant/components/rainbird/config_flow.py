"""Config flow for Rain Bird."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import async_timeout
from pyrainbird.async_client import (
    AsyncRainbirdClient,
    AsyncRainbirdController,
    RainbirdApiException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_DURATION,
    CONF_IMPORTED_NAMES,
    CONF_SERIAL_NUMBER,
    CONF_ZONES,
    DEFAULT_TRIGGER_TIME_MINUTES,
    DOMAIN,
    TIMEOUT_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


class ConfigFlowError(Exception):
    """Error raised during a config flow."""

    def __init__(self, message: str, error_code: str) -> None:
        """Initialize ConfigFlowError."""
        super().__init__(message)
        self.error_code = error_code


class RainbirdConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rain Bird."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RainBirdOptionsFlowHandler:
        """Define the config flow to handle options."""
        return RainBirdOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the Rain Bird device."""
        error_code: str | None = None
        if user_input:
            try:
                serial_number = await self._test_connection(
                    user_input[CONF_HOST], user_input[CONF_PASSWORD]
                )
            except ConfigFlowError as err:
                _LOGGER.error("Error during config flow: %s", err)
                error_code = err.error_code
            else:
                return await self.async_finish(
                    serial_number,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SERIAL_NUMBER: serial_number,
                    },
                    options={ATTR_DURATION: DEFAULT_TRIGGER_TIME_MINUTES},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors={"base": error_code} if error_code else None,
        )

    async def _test_connection(self, host: str, password: str) -> str:
        """Test the connection and return the device serial number.

        Raises a ConfigFlowError on failure.
        """
        controller = AsyncRainbirdController(
            AsyncRainbirdClient(
                async_get_clientsession(self.hass),
                host,
                password,
            )
        )
        try:
            async with async_timeout.timeout(TIMEOUT_SECONDS):
                return await controller.get_serial_number()
        except asyncio.TimeoutError as err:
            raise ConfigFlowError(
                f"Timeout connecting to Rain Bird controller: {str(err)}",
                "timeout_connect",
            ) from err
        except RainbirdApiException as err:
            raise ConfigFlowError(
                f"Error connecting to Rain Bird controller: {str(err)}",
                "cannot_connect",
            ) from err

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: config[CONF_HOST]})
        try:
            serial_number = await self._test_connection(
                config[CONF_HOST], config[CONF_PASSWORD]
            )
        except ConfigFlowError as err:
            _LOGGER.error("Error during config import: %s", err)
            return self.async_abort(reason=err.error_code)

        data = {
            CONF_HOST: config[CONF_HOST],
            CONF_PASSWORD: config[CONF_PASSWORD],
            CONF_SERIAL_NUMBER: serial_number,
        }
        names: dict[str, str] = {}
        for zone, zone_config in config.get(CONF_ZONES, {}).items():
            if name := zone_config.get(CONF_FRIENDLY_NAME):
                names[str(zone)] = name
        if names:
            data[CONF_IMPORTED_NAMES] = names
        return await self.async_finish(
            serial_number,
            data=data,
            options={
                ATTR_DURATION: config.get(ATTR_DURATION, DEFAULT_TRIGGER_TIME_MINUTES),
            },
        )

    async def async_finish(
        self,
        serial_number: str,
        data: dict[str, Any],
        options: dict[str, Any],
    ) -> FlowResult:
        """Create the config entry."""
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=data[CONF_HOST],
            data=data,
            options=options,
        )


class RainBirdOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a RainBird options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize RainBirdOptionsFlowHandler."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        ATTR_DURATION,
                        default=self.config_entry.options[ATTR_DURATION],
                    ): cv.positive_int,
                }
            ),
        )
