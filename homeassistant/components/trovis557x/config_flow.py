"""Config flow for Trovis 557x."""

from typing import Any

from modbus_connection import ModbusError
from trovis_modbus import Trovis557x
import voluptuous as vol

from homeassistant.components.modbus_connection import (
    ConnectionNotReady,
    async_get_unit,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    ConfigEntrySelector,
    ConfigEntrySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import CONF_CONNECTION, CONF_UNIT_ID, DEFAULT_UNIT_ID, DOMAIN

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_CONNECTION): ConfigEntrySelector(
            ConfigEntrySelectorConfig(integration="modbus_connection")
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): NumberSelector(
            NumberSelectorConfig(min=1, max=255, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class TrovisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trovis 557x."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a Modbus connection and unit ID, then read the model for the title."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_CONNECTION]}_{int(user_input[CONF_UNIT_ID])}"
            )
            self._abort_if_unique_id_configured()
            if (title := await self._async_title(user_input)) is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def _async_title(self, data: dict[str, Any]) -> str | None:
        """Read the controller model for the entry title, or None if unreachable."""
        try:
            unit = async_get_unit(
                self.hass, data[CONF_CONNECTION], int(data[CONF_UNIT_ID])
            )
            device = Trovis557x(unit)
            await device.info.async_update()
        except ConnectionNotReady, ModbusError, OSError, ValueError:
            return None
        return device.info.model
