"""Adding a WS90 by address."""

import logging
from typing import Any, override

from ecowitt_ws90_modbus import WS90
from modbus_connection import ModbusError, ModbusTcpParams
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

from .const import CONF_UNIT_ID, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN

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


class EcowittWS90ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecowitt WS90."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an address and check a WS90 answers there."""
        errors: dict[str, str] = {}

        if user_input is not None:
            params = ModbusTcpParams(
                host=user_input[CONF_HOST], port=user_input[CONF_PORT], framer="rtu"
            )
            try:
                async with async_get_temporary_unit(
                    self.hass, params, user_input[CONF_UNIT_ID]
                ) as unit:
                    device = WS90(unit)
                    await device.async_update()
            except (ModbusError, HomeAssistantError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if device.info.model != "WS90":
                    errors["base"] = "not_a_ws90"
                else:
                    # Stable across address changes, which a host, port, or
                    # unit ID is not.
                    await self.async_set_unique_id(f"{device.info.device_id:08x}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"WS90 ({user_input[CONF_HOST]})", data=user_input
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
