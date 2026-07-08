"""Config flow for the NeoPool integration."""

from typing import Any, override

from neopool_modbus import async_probe_serial
from neopool_modbus.exceptions import (
    NeoPoolConnectionError,
    NeoPoolModbusError,
    NeoPoolTimeoutError,
)
from neopool_modbus.registers import DEFAULT_MODBUS_FRAMER
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import CURRENT_VERSION, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN
from .coordinator import NeoPoolConfigEntry
from .options_flow import NeoPoolOptionsFlowHandler


async def _async_probe(user_input: dict[str, Any]) -> tuple[str | None, str | None]:
    """Probe a device using user-supplied connection parameters."""
    try:
        serial = await async_probe_serial(
            user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            unit_id=user_input["unit_id"],
            framer=user_input["modbus_framer"],
        )
    except NeoPoolConnectionError, NeoPoolTimeoutError:
        return None, "cannot_connect"
    except NeoPoolModbusError:
        return None, "cannot_read_modbus"
    return serial, None


class NeoPoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NeoPool."""

    VERSION = CURRENT_VERSION

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: NeoPoolConfigEntry,
    ) -> NeoPoolOptionsFlowHandler:
        """Return the options flow handler."""
        return NeoPoolOptionsFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                vol.Optional("unit_id", default=DEFAULT_UNIT_ID): vol.Coerce(int),
                vol.Optional(
                    "modbus_framer",
                    default=DEFAULT_MODBUS_FRAMER,
                ): vol.In(("tcp", "rtu")),
            }
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            serial, error_key = await _async_probe(user_input)
            if error_key:
                errors[CONF_HOST] = error_key
            else:
                assert serial is not None
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
