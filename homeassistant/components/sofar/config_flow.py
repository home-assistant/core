"""Config flow for Sofar devices."""

import logging
from typing import Any, override

from modbus_connection import ModbusError, ModbusTcpParams
from sofar_modbus.modern.device import SofarInverter
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import CONF_UNIT_ID, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN

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
            params = ModbusTcpParams(
                host=user_input[CONF_HOST], port=user_input[CONF_PORT]
            )
            try:
                async with async_get_temporary_unit(
                    self.hass, params, user_input[CONF_UNIT_ID]
                ) as unit:
                    device = SofarInverter(unit)
                    await device.async_update()
            except (ModbusError, HomeAssistantError) as err:
                errors["base"] = "cannot_connect"
                description_placeholders["error"] = str(err)
            else:
                assert device.serial_number is not None
                if not device.inverter_type:
                    errors["base"] = "unrecognized_inverter"
                else:
                    await self.async_set_unique_id(device.serial_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=device.model or DEFAULT_NAME,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )
