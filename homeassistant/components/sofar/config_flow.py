"""TCP-only config flow (Phase 1); probes for unique_id and EPS support."""

import logging
from typing import TYPE_CHECKING, Any, override

from modbus_connection import ModbusError, ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from sofar_modbus.modern.device import SofarInverter, identify
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_READ_EPS,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            vol.Coerce(int),
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)
            ),
            vol.Coerce(int),
        ),
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
                    port=user_input[CONF_PORT],
                )
            )
            try:
                device = SofarInverter(
                    connection.for_unit(user_input[CONF_UNIT_ID]),
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
