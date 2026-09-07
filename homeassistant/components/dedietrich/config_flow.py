"""Config flow for De Dietrich Diematic devices."""

import logging
from typing import Any, override

from diematic_modbus import Diematic, DiematicISystem
from modbus_connection import ModbusError, ModbusTcpParams
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_SYSTEM,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MESSAGE_SPACING,
    MODBUS_FRAMER,
    SYSTEM_DIEMATIC_3,
    SYSTEM_DIEMATIC_4,
    SYSTEM_ISYSTEM,
)
from .device import build_device

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
        vol.Required(CONF_SYSTEM): SelectSelector(
            SelectSelectorConfig(
                options=[SYSTEM_DIEMATIC_3, SYSTEM_DIEMATIC_4, SYSTEM_ISYSTEM],
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_SYSTEM,
            )
        ),
    }
)


async def _async_probe(
    hass: HomeAssistant, host: str, port: int, unit_id: int, system: str
) -> Diematic | DiematicISystem:
    """Connect to the boiler and read its identity, or raise."""
    params = ModbusTcpParams(host=host, port=port, framer=MODBUS_FRAMER)
    async with async_get_temporary_unit(hass, params, unit_id) as unit:
        unit.set_message_spacing(MESSAGE_SPACING)
        device = build_device(unit, system)
        await device.async_update()
    return device


class DeDietrichConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a De Dietrich config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            try:
                device = await _async_probe(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_UNIT_ID],
                    user_input[CONF_SYSTEM],
                )
            except (ModbusError, HomeAssistantError) as err:
                errors["base"] = "cannot_connect"
                description_placeholders["error"] = str(err)
            else:
                self._async_abort_entries_match(
                    {
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                        CONF_SYSTEM: user_input[CONF_SYSTEM],
                    }
                )
                return self.async_create_entry(
                    title=str(device.identity.boiler_type) or DEFAULT_NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )
