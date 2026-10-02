"""Config flow for Sofar devices."""

from collections.abc import Mapping
import logging
from typing import Any, override

from modbus_connection import ModbusError, ModbusTcpParams
import probatio
from sofar_modbus.modern.device import SofarInverter

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import CONF_UNIT_ID, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)
            ),
            probatio.Coerce(int),
        ),
    }
)


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> SofarInverter:
    """Connect to the inverter and read its identity, or raise."""
    params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        device = await SofarInverter.async_detect(unit)
        await device.async_update()
    return device


class SofarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Sofar config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            device, errors, description_placeholders = await self._async_validate(
                user_input
            )
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.model or DEFAULT_NAME, data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating an existing entry's connection details."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            device, errors, description_placeholders = await self._async_validate(
                user_input
            )
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[SofarInverter | None, dict[str, str], dict[str, str]]:
        """Probe the inverter, returning it or the errors to show instead."""
        try:
            device = await _async_probe(self.hass, data)
        except (ModbusError, HomeAssistantError) as err:
            return None, {"base": "cannot_connect"}, {"error": str(err)}

        if not device.inverter_type:
            return None, {"base": "unrecognized_inverter"}, {}

        return device, {}, {}
