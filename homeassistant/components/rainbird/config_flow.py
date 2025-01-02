"""Config flow for Rain Bird."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from pyrainbird.async_client import AsyncRainbirdClient, AsyncRainbirdController
from pyrainbird.data import WifiParams
from pyrainbird.exceptions import RainbirdApiException, RainbirdAuthException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device_registry import format_mac

from . import RainbirdConfigEntry
from .const import (
    ATTR_DURATION,
    CONF_SERIAL_NUMBER,
    DEFAULT_TRIGGER_TIME_MINUTES,
    DOMAIN,
    TIMEOUT_SECONDS,
)
from .coordinator import async_create_clientsession

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
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


class RainbirdConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rain Bird."""

    host: str

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: RainbirdConfigEntry,
    ) -> RainBirdOptionsFlowHandler:
        """Define the config flow to handle options."""
        return RainBirdOptionsFlowHandler()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        self.host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                await self._test_connection(self.host, user_input[CONF_PASSWORD])
            except ConfigFlowError as err:
                _LOGGER.error("Error during config flow: %s", err)
                errors["base"] = err.error_code
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        clientsession = async_create_clientsession()
        controller = AsyncRainbirdController(
            AsyncRainbirdClient(
                clientsession,
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
        except TimeoutError as err:
            raise ConfigFlowError(
                f"Timeout connecting to Rain Bird controller: {err!s}",
                "timeout_connect",
            ) from err
        except RainbirdAuthException as err:
            raise ConfigFlowError(
                f"Authentication error connecting from Rain Bird controller: {err!s}",
                "invalid_auth",
            ) from err
        except RainbirdApiException as err:
            raise ConfigFlowError(
                f"Error connecting to Rain Bird controller: {err!s}",
                "cannot_connect",
            ) from err
        finally:
            await clientsession.close()

    async def async_finish(
        self,
        data: dict[str, Any],
        options: dict[str, Any],
    ) -> ConfigFlowResult:
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


class RainBirdOptionsFlowHandler(OptionsFlow):
    """Handle a RainBird options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
