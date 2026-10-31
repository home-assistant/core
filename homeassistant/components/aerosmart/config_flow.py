"""Config flow for aerosmart."""

from typing import Any, override

from aerosmart_modbus import AerosmartDevice
from modbus_connection import ModbusError
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_BAUDRATE,
    CONF_UNIT_HEAT_PUMP,
    CONF_UNIT_VENTILATION,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_UNIT_HEAT_PUMP,
    DEFAULT_UNIT_VENTILATION,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import create_modbus_params

_CONNECT_ERRORS = (ModbusError, HomeAssistantError, OSError, ValueError)

UNIT_ID_SCHEMA = NumberSelector(
    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
)

STEP_TCP = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
        ),
        probatio.Required(
            CONF_UNIT_VENTILATION, default=DEFAULT_UNIT_VENTILATION
        ): UNIT_ID_SCHEMA,
        probatio.Required(
            CONF_UNIT_HEAT_PUMP, default=DEFAULT_UNIT_HEAT_PUMP
        ): UNIT_ID_SCHEMA,
    }
)

STEP_SERIAL = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): NumberSelector(
            NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
        ),
        probatio.Required(
            CONF_UNIT_VENTILATION, default=DEFAULT_UNIT_VENTILATION
        ): UNIT_ID_SCHEMA,
        probatio.Required(
            CONF_UNIT_HEAT_PUMP, default=DEFAULT_UNIT_HEAT_PUMP
        ): UNIT_ID_SCHEMA,
    }
)


DESCRIPTION_PLACEHOLDERS = {
    "default_port": str(DEFAULT_PORT),
    "default_unit_heat_pump": str(DEFAULT_UNIT_HEAT_PUMP),
    "default_unit_ventilation": str(DEFAULT_UNIT_VENTILATION),
}


class AerosmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for aerosmart."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select a connection type."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a Modbus TCP gateway."""
        return await self._async_step_connection(TYPE_TCP, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a serial Modbus RTU connection."""
        return await self._async_step_connection(TYPE_SERIAL, user_input)

    async def _async_step_connection(
        self, connection_type: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Validate the controller connection and create an entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_integer_inputs(connection_type, user_input)
            if errors:
                return self.async_show_form(
                    step_id=connection_type,
                    data_schema=(
                        STEP_SERIAL if connection_type == TYPE_SERIAL else STEP_TCP
                    ),
                    errors=errors,
                    description_placeholders=DESCRIPTION_PLACEHOLDERS,
                )

            user_input = self._normalize_input(connection_type, user_input)
            if user_input[CONF_UNIT_VENTILATION] == user_input[CONF_UNIT_HEAT_PUMP]:
                errors["base"] = "same_unit"
            else:
                self._async_abort_entries_match(
                    {
                        key: value
                        for key, value in user_input.items()
                        if key != CONF_BAUDRATE
                    }
                )

                if not await self._async_can_connect(user_input):
                    errors["base"] = "cannot_connect"
                else:
                    # Another flow can create a matching entry while this one
                    # awaits the connection probe above.
                    self._async_abort_entries_match(
                        {
                            key: value
                            for key, value in user_input.items()
                            if key != CONF_BAUDRATE
                        }
                    )
                    return self.async_create_entry(title="aerosmart", data=user_input)

        return self.async_show_form(
            step_id=connection_type,
            data_schema=STEP_SERIAL if connection_type == TYPE_SERIAL else STEP_TCP,
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )

    @staticmethod
    def _validate_integer_inputs(
        connection_type: str, data: dict[str, Any]
    ) -> dict[str, str]:
        """Ensure selector values will not lose precision when stored as integers."""
        fields = [CONF_UNIT_VENTILATION, CONF_UNIT_HEAT_PUMP]
        fields.append(CONF_BAUDRATE if connection_type == TYPE_SERIAL else CONF_PORT)
        return {
            field: "invalid_integer"
            for field in fields
            if not isinstance(data[field], int | float)
            or not float(data[field]).is_integer()
        }

    async def _async_can_connect(self, data: dict[str, Any]) -> bool:
        """Probe both units and always release the temporary connection."""
        try:
            params = create_modbus_params(data)
            async with (
                async_get_temporary_unit(
                    self.hass, params, data[CONF_UNIT_VENTILATION]
                ) as unit_ventilation,
                async_get_temporary_unit(
                    self.hass, params, data[CONF_UNIT_HEAT_PUMP]
                ) as unit_heat_pump,
            ):
                AerosmartDevice.configure_units(unit_ventilation, unit_heat_pump)
                await unit_ventilation.read_holding_registers(1174, 2)
                await unit_heat_pump.read_holding_registers(1044, 2)
        except _CONNECT_ERRORS:
            return False
        return True

    @staticmethod
    def _normalize_input(connection_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize selector values before storing them."""
        normalized: dict[str, Any] = {
            CONF_TYPE: connection_type,
            CONF_UNIT_VENTILATION: int(data[CONF_UNIT_VENTILATION]),
            CONF_UNIT_HEAT_PUMP: int(data[CONF_UNIT_HEAT_PUMP]),
        }
        if connection_type == TYPE_SERIAL:
            normalized[CONF_DEVICE] = str(data[CONF_DEVICE])
            normalized[CONF_BAUDRATE] = int(data[CONF_BAUDRATE])
        else:
            normalized[CONF_HOST] = str(data[CONF_HOST]).strip().lower()
            normalized[CONF_PORT] = int(data[CONF_PORT])
        return normalized
