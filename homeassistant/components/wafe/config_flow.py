"""Config flow for WAFE heat recovery units."""

from collections.abc import Mapping
from typing import Any, override

from modbus_connection import ModbusError, ModbusTcpParams
import probatio
from wafe_modbus import WafeUnit

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

from .const import DOMAIN, MANUFACTURER, UNIT_ID

DEFAULT_PORT = 502

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
    }
)


class WafeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a WAFE config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask where the unit is, then check that it answers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            device, errors = await self._async_probe(user_input)
            if device is not None:
                if not device.unit_id:
                    return self.async_abort(reason="no_unit_id")
                await self.async_set_unique_id(str(device.unit_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_title(device), data=dict(user_input)
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def _async_probe(
        self, data: Mapping[str, Any]
    ) -> tuple[WafeUnit | None, dict[str, str]]:
        """Identify the unit behind these settings, or return the error to show."""
        params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
        try:
            async with async_get_temporary_unit(self.hass, params, UNIT_ID) as unit:
                device = WafeUnit(unit)
                await device.async_ensure_setup()
        except ModbusError, HomeAssistantError:
            return None, {"base": "cannot_connect"}
        return device, {}


def _title(device: WafeUnit) -> str:
    """Name the entry after the model, like the vendor app does."""
    model = device.model
    return f"{MANUFACTURER} {model.name}" if model is not None else MANUFACTURER
