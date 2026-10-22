"""Config flow for aerosmart."""

import logging
from typing import Any, override

from aerosmart_modbus import AerosmartDevice
from modbus_connection import ModbusError, ModbusTcpParams
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_UNIT_HEAT_PUMP,
    CONF_UNIT_VENTILATION,
    DEFAULT_PORT,
    DEFAULT_UNIT_HEAT_PUMP,
    DEFAULT_UNIT_VENTILATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_CONNECT_ERRORS = (ModbusError, HomeAssistantError, OSError, ValueError)

STEP_USER = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
        ),
        probatio.Required(
            CONF_UNIT_VENTILATION, default=DEFAULT_UNIT_VENTILATION
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
        ),
        probatio.Required(
            CONF_UNIT_HEAT_PUMP, default=DEFAULT_UNIT_HEAT_PUMP
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class AerosmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for aerosmart."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the TCP endpoint and both unit IDs."""
        return await self._async_step_connection(user_input)

    async def _async_step_connection(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Validate the controller connection and create an entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._normalize_input(user_input)
            if user_input[CONF_UNIT_VENTILATION] == user_input[CONF_UNIT_HEAT_PUMP]:
                errors["base"] = "same_unit"
            else:
                self._async_abort_entries_match(user_input)

                if not await self._async_can_connect(user_input):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title="aerosmart", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def _async_can_connect(self, data: dict[str, Any]) -> bool:
        """Probe both units and always release the temporary connection."""
        try:
            params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
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
        except _CONNECT_ERRORS as err:
            _LOGGER.warning("Failed to validate aerosmart connection: %s", err)
            return False
        return True

    @staticmethod
    def _normalize_input(data: dict[str, Any]) -> dict[str, Any]:
        """Normalize selector values before storing them."""
        return {
            CONF_HOST: str(data[CONF_HOST]).strip().lower(),
            CONF_PORT: int(data[CONF_PORT]),
            CONF_UNIT_VENTILATION: int(data[CONF_UNIT_VENTILATION]),
            CONF_UNIT_HEAT_PUMP: int(data[CONF_UNIT_HEAT_PUMP]),
        }
