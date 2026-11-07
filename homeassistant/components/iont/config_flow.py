"""Config flow to configure the IONT integration."""

from typing import Any, override

from modbus_connection import ModbusTcpParams
import probatio
from pyiont import IontCharger, IontConnectionError, IontError

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

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN, UNIT_ID

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(int),
        ),
    }
)


def _normalized(user_input: dict[str, Any]) -> dict[str, Any]:
    """Shape form input into config entry data.

    One connection is shared per host and port, so spelling matters.
    """
    return {
        CONF_HOST: user_input[CONF_HOST].lower(),
        CONF_PORT: user_input[CONF_PORT],
    }


class IontConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an IONT config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the charger's address, then probe it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _normalized(user_input)
            self._async_abort_entries_match(data)
            if not (errors := await self._async_validate(data)):
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of how the charger is reached."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _normalized(user_input)
            self._async_abort_entries_match(data)
            if not (errors := await self._async_validate(data)):
                return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def _async_validate(self, data: dict[str, Any]) -> dict[str, str]:
        """Probe the charger behind an address, returning form errors."""
        params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
        try:
            async with async_get_temporary_unit(self.hass, params, UNIT_ID) as unit:
                await IontCharger.async_probe(unit)
        except HomeAssistantError, IontConnectionError:
            # HomeAssistantError: the device is already in use over different
            # link settings, which one connection cannot honour.
            return {"base": "cannot_connect"}
        except IontError:
            return {"base": "no_iont_charger"}

        return {}
