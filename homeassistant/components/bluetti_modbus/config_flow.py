"""Config flow to configure the BLUETTI Modbus integration."""

from typing import Any, override

from modbus_connection import ModbusError, ModbusTcpParams
import probatio

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
from .device import restricted_device

STEP_USER = probatio.Schema(
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
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=247, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(int),
        ),
    }
)


class BluettiModbusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BLUETTI Modbus config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask where the device is, then probe it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # A link some entry already owns is rejected before the device is
            # probed, so a duplicate aborts even while the device is offline.
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                }
            )
            errors, serial = await self._async_validate(user_input)
            if not errors:
                assert (
                    serial is not None
                )  # only unset alongside a non-empty errors dict
                # Catches the same device already added under a different
                # link (moved to a new address, for example).
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Balco260", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], str | None]:
        """Probe the device, returning form errors and its serial number.

        The serial number is ``None`` only alongside a non-empty errors
        dict - a successful probe always confirms one.
        """
        params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
        try:
            async with async_get_temporary_unit(
                self.hass, params, data[CONF_UNIT_ID]
            ) as unit:
                device = restricted_device(unit)
                await device.async_update_with_retry()
        except HomeAssistantError:
            # The address is already claimed by another entry with different
            # link settings, which one shared connection cannot honour - a
            # deterministic conflict, not a transient connection failure, so
            # tell the user to fix it rather than to retry.
            return {"base": "link_settings_in_use"}, None
        except ModbusError, TimeoutError:
            # TimeoutError: async_update_with_retry()'s own internal budget
            # (see its docstring) can expire without ever raising a
            # ModbusError - a slow device, not a protocol-level failure, but
            # the same "can't connect right now" outcome from here.
            return {"base": "cannot_connect"}, None

        serial = device.values.get("d_serial")
        if not serial:
            # 0 isn't a real Balco260 serial - the same "can't identify
            # this device" outcome as one that didn't answer at all.
            return {"base": "cannot_connect"}, None
        return {}, str(serial)
