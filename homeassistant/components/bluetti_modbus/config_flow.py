"""Config flow to configure the BLUETTI Modbus integration."""

from typing import Any, override

from bluetti_modbus_lib.devices.getter import get_device
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

from .const import (
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DEVICE_TYPE_BALCO260,
    DOMAIN,
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=247, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
        ),
    }
)


def _normalized(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return config entry data with the host lowercased.

    homeassistant.components.modbus.connection keys its shared connections
    on ModbusTcpParams, comparing the host string as-is - two entries
    (or the same one re-added) spelling the same host with different case
    would be treated as different links instead of sharing one connection.
    """
    return {**user_input, CONF_HOST: user_input[CONF_HOST].lower()}


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
            data = _normalized(user_input)
            errors, serial = await self._async_validate(data)
            if not errors:
                assert (
                    serial is not None
                )  # only unset alongside a non-empty errors dict
                # Catches the same device already added under a different
                # link (moved to a new address, for example).
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                # Always checked too: this exact link claimed by some other
                # entry, whether or not either side has a serial number.
                self._async_abort_entries_match(
                    {
                        CONF_HOST: data[CONF_HOST],
                        CONF_PORT: data[CONF_PORT],
                        CONF_UNIT_ID: data[CONF_UNIT_ID],
                    }
                )
                return self.async_create_entry(title="Balco260", data=data)

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
                device = get_device(DEVICE_TYPE_BALCO260, unit)
                assert (
                    device is not None
                )  # DEVICE_TYPE_BALCO260 is always a known device type
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
