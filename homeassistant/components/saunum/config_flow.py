"""Config flow for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_SAUNA_TYPE_1_NAME,
    CONF_SAUNA_TYPE_2_NAME,
    CONF_SAUNA_TYPE_3_NAME,
    DEFAULT_DEVICE_ID,
    DEFAULT_PORT,
    DEFAULT_SAUNA_TYPE_1_NAME,
    DEFAULT_SAUNA_TYPE_2_NAME,
    DEFAULT_SAUNA_TYPE_3_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], flow: ConfigFlow
) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    port = data[CONF_PORT]

    client = AsyncModbusTcpClient(host=host, port=port, timeout=5)
    await client.connect()

    if not client.connected:
        raise ModbusException("Cannot connect")

    # Try to read a register to verify communication
    result = await client.read_holding_registers(
        address=0, count=1, device_id=DEFAULT_DEVICE_ID
    )
    if result.isError():
        raise ModbusException("Cannot read registers")

    client.close()


class LeilSaunaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Saunum Leil Sauna Control Unit."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LeilSaunaOptionsFlow:
        """Get the options flow for this handler."""
        return LeilSaunaOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input, self)

                # Set unique ID and check for duplicates
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
            except ModbusException:
                errors["base"] = "cannot_connect"
            except AbortFlow:
                raise
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Saunum Leil Sauna",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class LeilSaunaOptionsFlow(OptionsFlow):
    """Handle options flow for Saunum Leil Sauna Control Unit."""

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
                        CONF_SAUNA_TYPE_1_NAME,
                        default=self.config_entry.options.get(
                            CONF_SAUNA_TYPE_1_NAME, DEFAULT_SAUNA_TYPE_1_NAME
                        ),
                    ): cv.string,
                    vol.Optional(
                        CONF_SAUNA_TYPE_2_NAME,
                        default=self.config_entry.options.get(
                            CONF_SAUNA_TYPE_2_NAME, DEFAULT_SAUNA_TYPE_2_NAME
                        ),
                    ): cv.string,
                    vol.Optional(
                        CONF_SAUNA_TYPE_3_NAME,
                        default=self.config_entry.options.get(
                            CONF_SAUNA_TYPE_3_NAME,
                            DEFAULT_SAUNA_TYPE_3_NAME,
                        ),
                    ): cv.string,
                }
            ),
        )
