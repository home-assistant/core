"""Adding an inverter by address."""

import logging
from typing import Any, override

from kaco_modbus import KacoError, KacoInverter, NotAKacoInverterError
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


class KacoModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KACO Modbus."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an address and check a KACO inverter answers there."""
        errors: dict[str, str] = {}

        if user_input is not None:
            params = ModbusTcpParams(
                host=user_input[CONF_HOST], port=user_input[CONF_PORT]
            )
            try:
                async with async_get_temporary_unit(
                    self.hass, params, user_input[CONF_UNIT_ID]
                ) as unit:
                    device = KacoInverter(unit)
                    await device.async_update_readings()
            except NotAKacoInverterError:
                errors["base"] = "not_a_kaco_inverter"
            except KacoError:
                errors["base"] = "not_a_sunspec_inverter"
            except ModbusError, HomeAssistantError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                info = device.info
                assert info is not None
                # Stable across address changes, which a host or port is not.
                await self.async_set_unique_id(info.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.model, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
