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

    VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the TCP endpoint and both unit IDs."""
        return await self._async_step_connection(user_input, step_id="user")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the TCP endpoint and/or either unit ID of an existing entry."""
        return await self._async_step_connection(user_input, step_id="reconfigure")

    async def _async_step_connection(
        self, user_input: dict[str, Any] | None, *, step_id: str
    ) -> ConfigFlowResult:
        """Shared body for the initial and reconfigure steps.

        The unique ID is derived from exactly the fields this form lets the
        user change, so a reconfigure that doesn't touch any field recomputes
        the *same* unique ID as the entry being reconfigured -- checking that
        against ``_abort_if_unique_id_configured`` would always find itself
        and incorrectly abort. Only run the duplicate check when the
        recomputed unique ID actually differs from the reconfigured entry's
        current one.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._normalize_input(user_input)
            await self.async_set_unique_id(self._unique_id(user_input))
            if step_id == "reconfigure":
                reconfigure_entry = self._get_reconfigure_entry()
                if self.unique_id != reconfigure_entry.unique_id:
                    self._abort_if_unique_id_configured()
            else:
                self._abort_if_unique_id_configured()

            if not await self._async_can_connect(user_input):
                errors["base"] = "cannot_connect"
            elif step_id == "reconfigure":
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data=user_input,
                    unique_id=self.unique_id,
                )
            else:
                return self.async_create_entry(title="aerosmart", data=user_input)

        schema = STEP_USER
        if step_id == "reconfigure":
            # Prefill with what the user just submitted (so a validation error
            # doesn't discard their input); fall back to the entry's current
            # data on the form's first display.
            suggested = user_input or self._get_reconfigure_entry().data
            schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

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
            CONF_HOST: str(data[CONF_HOST]).strip(),
            CONF_PORT: int(data[CONF_PORT]),
            CONF_UNIT_VENTILATION: int(data[CONF_UNIT_VENTILATION]),
            CONF_UNIT_HEAT_PUMP: int(data[CONF_UNIT_HEAT_PUMP]),
        }

    @staticmethod
    def _unique_id(data: dict[str, Any]) -> str:
        """Return the identity of one installation endpoint."""
        return (
            f"{data[CONF_HOST].lower()}:{data[CONF_PORT]}"
            f"_{data[CONF_UNIT_VENTILATION]}_{data[CONF_UNIT_HEAT_PUMP]}"
        )
