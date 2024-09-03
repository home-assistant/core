"""OpenTherm Gateway config flow."""

from __future__ import annotations

import asyncio
from typing import Any

import pyotgw
from pyotgw import vars as gw_vars
from serial import SerialException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import DOMAIN
from .const import (
    CONF_FLOOR_TEMP,
    CONF_READ_PRECISION,
    CONF_SET_PRECISION,
    CONF_TEMPORARY_OVRD_MODE,
    CONNECTION_TIMEOUT,
    OpenThermDataSource,
)


class OpenThermGwConfigFlow(ConfigFlow, domain=DOMAIN):
    """OpenTherm Gateway Config Flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OpenThermGwOptionsFlow:
        """Get the options flow for this handler."""
        return OpenThermGwOptionsFlow(config_entry)

    async def async_step_init(
        self, info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle config flow initiation."""
        if info:
            name = info[CONF_NAME]
            device = info[CONF_DEVICE]
            gw_id = cv.slugify(info.get(CONF_ID, name))

            entries = [e.data for e in self._async_current_entries()]

            if gw_id in [e[CONF_ID] for e in entries]:
                return self._show_form({"base": "id_exists"})

            if device in [e[CONF_DEVICE] for e in entries]:
                return self._show_form({"base": "already_configured"})

            async def test_connection():
                """Try to connect to the OpenTherm Gateway."""
                otgw = pyotgw.OpenThermGateway()
                status = await otgw.connect(device)
                await otgw.disconnect()
                if not status:
                    raise ConnectionError
                return status[OpenThermDataSource.GATEWAY].get(gw_vars.OTGW_ABOUT)

            try:
                async with asyncio.timeout(CONNECTION_TIMEOUT):
                    await test_connection()
            except TimeoutError:
                return self._show_form({"base": "timeout_connect"})
            except (ConnectionError, SerialException):
                return self._show_form({"base": "cannot_connect"})

            return self._create_entry(gw_id, name, device)

        return self._show_form()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual initiation of the config flow."""
        return await self.async_step_init(user_input)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import an OpenTherm Gateway device as a config entry.

        This flow is triggered by `async_setup` for configured devices.
        """
        formatted_config = {
            CONF_NAME: import_data.get(CONF_NAME, import_data[CONF_ID]),
            CONF_DEVICE: import_data[CONF_DEVICE],
            CONF_ID: import_data[CONF_ID],
        }
        return await self.async_step_init(info=formatted_config)

    def _show_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show the config flow form with possible errors."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_DEVICE): str,
                    vol.Optional(CONF_ID): str,
                }
            ),
            errors=errors or {},
        )

    def _create_entry(self, gw_id, name, device):
        """Create entry for the OpenTherm Gateway device."""
        return self.async_create_entry(
            title=name, data={CONF_ID: gw_id, CONF_DEVICE: device, CONF_NAME: name}
        )


class OpenThermGwOptionsFlow(OptionsFlow):
    """Handle opentherm_gw options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the opentherm_gw options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_READ_PRECISION,
                        default=self.config_entry.options.get(CONF_READ_PRECISION, 0),
                    ): vol.All(
                        vol.Coerce(float),
                        vol.In(
                            [0, PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
                        ),
                    ),
                    vol.Optional(
                        CONF_SET_PRECISION,
                        default=self.config_entry.options.get(CONF_SET_PRECISION, 0),
                    ): vol.All(
                        vol.Coerce(float),
                        vol.In(
                            [0, PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
                        ),
                    ),
                    vol.Optional(
                        CONF_TEMPORARY_OVRD_MODE,
                        default=self.config_entry.options.get(
                            CONF_TEMPORARY_OVRD_MODE, True
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_FLOOR_TEMP,
                        default=self.config_entry.options.get(CONF_FLOOR_TEMP, False),
                    ): bool,
                }
            ),
        )
