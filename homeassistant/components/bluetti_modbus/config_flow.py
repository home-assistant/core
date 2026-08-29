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
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_DEVICE_TYPE,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DEVICE_TYPES,
    DOMAIN,
)
from .entity import device_name

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
        vol.Required(CONF_DEVICE_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=list(DEVICE_TYPES), translation_key=CONF_DEVICE_TYPE
            )
        ),
    }
)


def _normalized(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return config entry data with the host spelling normalized.

    One connection is shared per host and port (see homeassistant.components
    .modbus.connection), so spelling matters.
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
                if serial is not None:
                    # Catches the same device already added under a
                    # different link (moved to a new address, for example).
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
                return self.async_create_entry(
                    title=device_name(data[CONF_DEVICE_TYPE]), data=data
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of how the device is reached.

        The device may move to another address or device ID, but it must
        stay the same device: where the entry was identified by serial
        number, a reconfigure probe that returns a different one (or none at
        all) is rejected rather than silently adopted.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            data = _normalized(user_input)
            errors, serial = await self._async_validate(data)
            if not errors:
                if entry.unique_id is not None and serial != entry.unique_id:
                    return self.async_abort(reason="wrong_device")
                # Always checked too: this exact link claimed by some other
                # entry, whether or not either side has a serial number.
                self._async_abort_entries_match(
                    {
                        CONF_HOST: data[CONF_HOST],
                        CONF_PORT: data[CONF_PORT],
                        CONF_UNIT_ID: data[CONF_UNIT_ID],
                    }
                )
                return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER, user_input or entry.data
            ),
            errors=errors,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], str | None]:
        """Probe the device, returning form errors and its serial number.

        The serial number is ``None`` both on failure and when the device
        type doesn't report one over Modbus.
        """
        params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
        try:
            async with async_get_temporary_unit(
                self.hass, params, data[CONF_UNIT_ID]
            ) as unit:
                device = get_device(data[CONF_DEVICE_TYPE], unit)
                if device is None:
                    return {"base": "unsupported_device_type"}, None
                # Confirms the picked model's registers answer, not that the
                # device is one - EP2000's map is a near-subset of Balco260's
                # at identical addresses, so a Balco260 answers as an EP2000
                # too. Telling them apart needs a real distinguishing register
                # confirmed against actual EP2000 hardware, which isn't
                # available yet.
                await device.async_update_with_retry()
        except HomeAssistantError:
            # The address is already claimed by another entry with different
            # link settings, which one shared connection cannot honour - a
            # deterministic conflict, not a transient connection failure, so
            # tell the user to fix it rather than to retry.
            return {"base": "link_settings_in_use"}, None
        except (ModbusError, TimeoutError):
            # TimeoutError: async_update_with_retry()'s own internal budget
            # (see its docstring) can expire without ever raising a
            # ModbusError - a slow device, not a protocol-level failure, but
            # the same "can't connect right now" outcome from here.
            return {"base": "cannot_connect"}, None

        serial = device.values.get("d_serial")
        return {}, str(serial) if serial is not None else None
