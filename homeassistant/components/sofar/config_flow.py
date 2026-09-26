"""Config flow for Sofar devices."""

from collections.abc import Mapping
import logging
from typing import Any, override

from modbus_connection import ModbusError
import probatio
from sofar_modbus.modern.device import SofarInverter

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)

from .const import (
    CONF_BAUDRATE,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import create_modbus_params

_LOGGER = logging.getLogger(__name__)

STEP_RECONFIGURE_SERIAL = "reconfigure_serial"
STEP_RECONFIGURE_TCP = "reconfigure_tcp"

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)

STEP_TCP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)

STEP_SERIAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): probatio.All(
            NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)


def _needs_relink(entry: ConfigEntry, data: Mapping[str, Any]) -> bool:
    """Whether probing these settings clashes with the link in use.

    One connection cannot serve two sets of line settings at once.
    """
    if entry.state not in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
        return False

    current = create_modbus_params(entry.data)
    new = create_modbus_params(data)

    return new.endpoint == current.endpoint and new != current


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> SofarInverter:
    """Connect to the inverter and read its identity, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        device = SofarInverter(unit)
        await device.async_update()
    return device


class SofarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Sofar config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the inverter is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an inverter reached over the network."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an inverter reached over a serial port."""
        return await self._async_step_link(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the inverter behind them."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            device, errors, description_placeholders = await self._async_validate(data)
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.model or DEFAULT_NAME, data=data
                )

        return self.async_show_form(
            step_id=connection_type,
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the inverter is reached from now on."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[STEP_RECONFIGURE_TCP, STEP_RECONFIGURE_SERIAL],
        )

    async def async_step_reconfigure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this inverter over the network from now on."""
        return await self._async_step_relink(
            STEP_RECONFIGURE_TCP, TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this inverter over a serial port from now on."""
        return await self._async_step_relink(
            STEP_RECONFIGURE_SERIAL, TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_relink(
        self,
        step_id: str,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the entry's own inverter."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}

            relinking = False
            if _needs_relink(entry, data):
                relinking = await self.hass.config_entries.async_unload(entry.entry_id)

            device, errors, description_placeholders = await self._async_validate(data)
            probed = device.serial_number if device is not None else None

            if relinking and probed != entry.unique_id:
                await self.hass.config_entries.async_setup(entry.entry_id)

            if device is not None:
                await self.async_set_unique_id(probed)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=data)

        suggested = user_input or (
            entry.data
            if entry.data.get(CONF_TYPE, TYPE_TCP) == connection_type
            else {CONF_UNIT_ID: entry.data[CONF_UNIT_ID]}
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[SofarInverter | None, dict[str, str], dict[str, str]]:
        """Probe the inverter, returning it or the errors to show instead."""
        try:
            device = await _async_probe(self.hass, data)
        except (ModbusError, HomeAssistantError) as err:
            return None, {"base": "cannot_connect"}, {"error": str(err)}

        if not device.inverter_type:
            return None, {"base": "unrecognized_inverter"}, {}

        return device, {}, {}
