"""Config flow to configure the SolarEdge Modbus integration."""

from collections.abc import Mapping
from typing import Any, override

from solaredged import SolarEdge, SolarEdgeConnectionError, SolarEdgeError
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import CONF_UNIT_ID, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN, TYPE_TCP
from .entity import inverter_name
from .helpers import create_modbus_params

SECTION_MORE_OPTIONS = "more_options"

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
        # Almost every inverter answers on the factory-default device ID, so
        # that setting is tucked away in a collapsed section.
        vol.Required(SECTION_MORE_OPTIONS): section(
            vol.Schema(
                {
                    vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=247, step=1, mode=NumberSelectorMode.BOX
                            )
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
            {"collapsed": True},
        ),
    }
)


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten the sectioned form input into config entry data."""
    data = {CONF_TYPE: TYPE_TCP, **user_input}
    data[CONF_UNIT_ID] = data.pop(SECTION_MORE_OPTIONS)[CONF_UNIT_ID]
    # One connection is shared per host and port, so spelling matters.
    data[CONF_HOST] = data[CONF_HOST].lower()

    return data


def _sectioned(data: Mapping[str, Any]) -> dict[str, Any]:
    """Shape config entry data back into the sectioned form input."""
    return {
        CONF_HOST: data[CONF_HOST],
        CONF_PORT: data[CONF_PORT],
        SECTION_MORE_OPTIONS: {CONF_UNIT_ID: data[CONF_UNIT_ID]},
    }


class SolarEdgeModbusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a SolarEdge Modbus config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask where the inverter is, then probe it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _flatten(user_input)
            errors, solaredge = await self._async_validate(data)
            if solaredge is not None:
                await self.async_set_unique_id(solaredge.common.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=inverter_name(solaredge.common.model), data=data
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of how the inverter is reached.

        The inverter may move to another address or device ID (a new gateway, a
        changed setting), but it must stay the same inverter: the probed serial
        number has to match the entry's unique ID.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            data = _flatten(user_input)
            errors, solaredge = await self._async_validate(data)

            if solaredge is not None:
                if solaredge.common.serial_number == entry.unique_id:
                    return self.async_update_reload_and_abort(entry, data_updates=data)
                return self.async_abort(reason="wrong_device")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER, user_input or _sectioned(entry.data)
            ),
            errors=errors,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], SolarEdge | None]:
        """Probe the inverter, returning form errors and the probed device."""
        try:
            async with async_get_temporary_unit(
                self.hass, create_modbus_params(data), data[CONF_UNIT_ID]
            ) as unit:
                solaredge = await SolarEdge.async_probe(unit)
                # Identity (serial number, model name) is read on the first refresh.
                await solaredge.async_update()
        except HomeAssistantError, SolarEdgeConnectionError:
            # HomeAssistantError: the device is already in use over different
            # link settings, which one connection cannot honour.
            return {"base": "cannot_connect"}, None
        except SolarEdgeError:
            return {"base": "no_solaredge_device"}, None

        if solaredge.is_ev_charger:
            return {"base": "ev_charger"}, None

        if not solaredge.common.serial_number:
            return {"base": "no_serial_number"}, None

        return {}, solaredge
