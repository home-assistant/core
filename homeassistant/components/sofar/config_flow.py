"""TCP-only config flow (Phase 1); probes for unique_id and EPS support."""

import logging
from typing import TYPE_CHECKING, Any, override

from modbus_connection import ModbusError, ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from sofar_modbus.modern.device import SofarInverter, identify
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

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
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(autocomplete="url")),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MODBUS_ADDR, default=DEFAULT_MODBUS_ADDR): int,
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
                    read_eps=True,
                )
                report = await device.async_update()
            except ModbusError:
                errors["base"] = "cannot_connect"
            else:
                if TYPE_CHECKING:
                    assert device.serial_number is not None
                # inverter_type always carries the EPS bit from read_eps=True,
                # so check identify() directly instead of inverter_type.
                if not identify(device.serial_number)[0]:
                    errors["base"] = "unrecognized_inverter"
                else:
                    await self.async_set_unique_id(device.serial_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=device.model or DEFAULT_NAME,
                        data={
                            **user_input,
                            CONF_READ_EPS: "eps" in report.updated,
                        },
                    )
            finally:
                await connection.close()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
