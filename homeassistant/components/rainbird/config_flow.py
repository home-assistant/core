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
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_DURATION, DOMAIN, TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


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
        _LOGGER.debug("async_step_user=%s", user_input)
        if user_input:
            try:
                serial_number = await self._test_connection(
                    user_input[CONF_HOST], user_input[CONF_PASSWORD]
                )
            except asyncio.TimeoutError as exc:
                _LOGGER.error("Timeout connecting to Rain Bird controller: %s", exc)
                error_code = "timeout_connect"
            except RainbirdApiException as exc:
                _LOGGER.error("Error connecting to Rain Bird controller: %s", exc)
                error_code = "cannot_connect"
            else:
                return await self.async_finish(serial_number, user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors={"base": error_code} if error_code else None,
        )

    async def _test_connection(self, host: str, password: str) -> str:
        """Test the connection and return the device serial number.

        Raises a TimeoutError or RainbirdApiException on failure.
        """
        controller = AsyncRainbirdController(
            AsyncRainbirdClient(
                async_get_clientsession(self.hass),
                host,
                password,
            )
        )
        async with async_timeout.timeout(TIMEOUT_SECONDS):
            return await controller.get_serial_number()

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == entry.data[CONF_HOST]:
                return self.async_abort(reason="already_configured")
        try:
            serial_number = await self._test_connection(
                config[CONF_HOST], config[CONF_PASSWORD]
            )
        except asyncio.TimeoutError as exc:
            _LOGGER.error("Timeout connecting to Rain Bird controller: %s", exc)
            return self.async_abort(reason="timeout_connect")
        except RainbirdApiException as exc:
            _LOGGER.error("Error connecting to Rain Bird controller: %s", exc)
            return self.async_abort(reason="cannot_connect")
        return await self.async_finish(serial_number, config)

    async def async_finish(
        self,
        serial_number: str,
        data: dict[str, Any],
        options: dict[str, Any] | None = None,
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
                        default=self.config_entry.options.get(
                            ATTR_DURATION,
                        ),
                    ): cv.positive_int,
                }
            ),
        )
