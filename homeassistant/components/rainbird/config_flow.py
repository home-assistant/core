"""Config flow for Rain Bird."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyrainbird.async_client import (
    AsyncRainbirdClient,
    AsyncRainbirdController,
    RainbirdApiException,
)
from pyrainbird.data import WifiParams
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import (
    ATTR_DURATION,
    CONF_SERIAL_NUMBER,
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
                serial_number, wifi_params = await self._test_connection(
                    user_input[CONF_HOST], user_input[CONF_PASSWORD]
                )
            except ConfigFlowError as err:
                _LOGGER.error("Error during config flow: %s", err)
                error_code = err.error_code
            else:
                return await self.async_finish(
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SERIAL_NUMBER: serial_number,
                        CONF_MAC: wifi_params.mac_address,
                    },
                    options={ATTR_DURATION: DEFAULT_TRIGGER_TIME_MINUTES},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors={"base": error_code} if error_code else None,
        )

    async def _test_connection(
        self, host: str, password: str
    ) -> tuple[str, WifiParams]:
        """Test the connection and return the device identifiers.

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
            async with asyncio.timeout(TIMEOUT_SECONDS):
                return await asyncio.gather(
                    controller.get_serial_number(),
                    controller.get_wifi_params(),
                )
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

    async def async_finish(
        self,
        data: dict[str, Any],
        options: dict[str, Any],
    ) -> FlowResult:
        """Create the config entry."""
        # The integration has historically used a serial number, but not all devices
        # historically had a valid one. Now the mac address is used as a unique id
        # and serial is still persisted in config entry data in case it is needed
        # in the future.
        # Either way, also prevent configuring the same host twice.
        await self.async_set_unique_id(format_mac(data[CONF_MAC]))
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: data[CONF_HOST],
                CONF_PASSWORD: data[CONF_PASSWORD],
            }
        )
        self._async_abort_entries_match(
            {
                CONF_HOST: data[CONF_HOST],
                CONF_PASSWORD: data[CONF_PASSWORD],
            }
        )
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
