"""Adding an inverter by address, and pointing one at a new address."""

import logging
from typing import Any, override

from kaco_modbus import (
    DeviceInfo as KacoDeviceInfo,
    KacoError,
    KacoInverter,
    NotAKacoInverterError,
)
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


async def _async_probe(hass: HomeAssistant, user_input: dict[str, Any]) -> KacoInverter:
    """Read the inverter answering at an address, or raise."""
    params = ModbusTcpParams(host=user_input[CONF_HOST], port=user_input[CONF_PORT])
    async with async_get_temporary_unit(hass, params, user_input[CONF_UNIT_ID]) as unit:
        device = KacoInverter(unit)
        await device.async_update_readings()
    return device


class KacoModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KACO Modbus."""

    VERSION = 1

    async def _async_identify(
        self, user_input: dict[str, Any]
    ) -> tuple[KacoDeviceInfo | None, dict[str, str]]:
        """Return what answers at an address, or the errors to show instead."""
        try:
            device = await _async_probe(self.hass, user_input)
        except NotAKacoInverterError:
            return None, {"base": "not_a_kaco_inverter"}
        except KacoError:
            return None, {"base": "not_a_sunspec_inverter"}
        except ModbusError, HomeAssistantError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}

        info = device.info
        assert info is not None
        return info, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an address and check a KACO inverter answers there."""
        errors: dict[str, str] = {}

        if user_input is not None:
            info, errors = await self._async_identify(user_input)
            if info is not None:
                # Stable across address changes, which a host or port is not.
                await self.async_set_unique_id(info.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.model, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at the address the inverter moved to."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            info, errors = await self._async_identify(user_input)
            if info is not None:
                await self.async_set_unique_id(info.serial_number)
                # Another serial is a different inverter, not a moved one.
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
        )
