"""Config flow — TCP only for Phase 1.

Probes the device to get its serial number for the unique_id.
"""

import logging
from typing import TYPE_CHECKING, Any, override

from modbus_connection import ModbusError, ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from sofar_modbus.modern.device import SofarInverter
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import TextSelector

from .const import (
    CONF_MODBUS_ADDR,
    CONF_READ_EPS,
    DEFAULT_MODBUS_ADDR,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MODBUS_ADDR, default=DEFAULT_MODBUS_ADDR): int,
        vol.Optional(CONF_READ_EPS, default=False): bool,
    }
)


class SofarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Sofar Modbus config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            connection = ModbusConnection(
                ModbusTcpParams(
                    host=user_input[CONF_HOST],
                    port=user_input.get(CONF_PORT, DEFAULT_PORT),
                )
            )
            try:
                device = SofarInverter(
                    connection.for_unit(
                        int(user_input.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR))
                    ),
                    read_eps=user_input.get(CONF_READ_EPS, False),
                )
                await device.async_update()
            except ModbusError:
                errors["base"] = "cannot_connect"
            else:
                if not device.inverter_type:
                    errors["base"] = "unrecognized_inverter"
                else:
                    if TYPE_CHECKING:
                        assert device.serial_number is not None
                    await self.async_set_unique_id(device.serial_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=device.model or DEFAULT_NAME, data=user_input
                    )
            finally:
                await connection.close()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
