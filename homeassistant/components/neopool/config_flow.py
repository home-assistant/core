"""Config flow for the NeoPool integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from neopool_modbus import async_probe_serial_unit
from neopool_modbus.exceptions import NeoPoolModbusError, NeoPoolTimeoutError
from neopool_modbus.registers import DEFAULT_MODBUS_FRAMER
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
)

from .const import (
    CONF_BAUDRATE,
    CONF_MODBUS_FRAMER,
    CONF_UNIT_ID,
    CONF_USE_AUX1,
    CONF_USE_AUX2,
    CONF_USE_AUX3,
    CONF_USE_AUX4,
    CONF_USE_COVER_SENSOR,
    CONF_USE_LIGHT,
    CURRENT_VERSION,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .coordinator import NeoPoolConfigEntry
from .helpers import build_modbus_params

_LOGGER = logging.getLogger(__name__)

# The device ID is a collapsed afterthought: most installs leave it at 1.
SECTION_MORE_OPTIONS = "more_options"

_MORE_OPTIONS = {
    probatio.Required(SECTION_MORE_OPTIONS): section(
        probatio.Schema(
            {
                probatio.Optional(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.BOX, min=1, max=247
                        )
                    ),
                    probatio.Coerce(int),
                ),
            }
        ),
        SectionConfig(collapsed=True),
    )
}

STEP_TCP = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Coerce(int),
        probatio.Optional(
            CONF_MODBUS_FRAMER, default=DEFAULT_MODBUS_FRAMER
        ): probatio.In(("tcp", "rtu")),
        **_MORE_OPTIONS,
    }
)

STEP_SERIAL = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1)
        ),
        **_MORE_OPTIONS,
    }
)


def _flatten(connection_type: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten the sectioned step input into config entry data."""
    data = {CONF_TYPE: connection_type, **user_input}
    data[CONF_UNIT_ID] = data.pop(SECTION_MORE_OPTIONS)[CONF_UNIT_ID]
    return data


def _sectioned(data: dict[str, Any]) -> dict[str, Any]:
    """Shape config entry data back into the sectioned step input."""
    return {
        **{key: value for key, value in data.items() if key != CONF_UNIT_ID},
        SECTION_MORE_OPTIONS: {CONF_UNIT_ID: data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)},
    }


async def _async_probe(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Probe a device through a temporary shared unit on its link.

    Borrowing a temporary unit means the probe speaks over the same connection a
    running entry would, so TCP and serial links are reached identically and a
    device already in use on different settings is reported rather than clashed.
    """
    try:
        async with async_get_temporary_unit(
            hass, build_modbus_params(data), data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
        ) as unit:
            serial = await async_probe_serial_unit(unit)
    except HomeAssistantError:
        # The device is already in use over different link settings, which one
        # shared connection cannot honour.
        return None, "cannot_connect"
    except NeoPoolTimeoutError:
        return None, "cannot_connect"
    except NeoPoolModbusError:
        return None, "cannot_read_modbus"
    return serial, None


def _needs_relink(entry: NeoPoolConfigEntry, data: Mapping[str, Any]) -> bool:
    """Whether probing these settings clashes with the connection in use.

    One connection is shared per endpoint and cannot serve two sets of line
    settings at once, so changing the line settings of the port an entry polls
    (a direct serial link's baud rate) needs that entry off the bus before the
    new settings can be probed. An entry waiting to retry counts as being on the
    bus; unloading it cancels the retry.
    """
    if entry.state not in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
        return False

    current = build_modbus_params(entry.data)
    new = build_modbus_params(data)

    return new.endpoint == current.endpoint and new != current


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
        """Let the user pick how the controller is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a controller reached over the network."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a controller reached over a serial port."""
        return await self._async_step_link(TYPE_SERIAL, STEP_SERIAL, user_input)

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the controller behind them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _flatten(connection_type, user_input)
            serial, error_key = await _async_probe(self.hass, data)
            if error_key:
                errors["base"] = error_key
            else:
                assert serial is not None
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                title = (
                    data[CONF_HOST]
                    if connection_type == TYPE_TCP
                    else data[CONF_DEVICE]
                )
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id=connection_type,
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry.

        The controller may move to another address or port (a new gateway, a
        rewired bus), but it must stay the same controller: the probed serial
        number has to match the entry's unique id. The connection type is fixed
        at the one the entry was created with.
        """
        entry = self._get_reconfigure_entry()
        connection_type = entry.data.get(CONF_TYPE, TYPE_TCP)
        schema = STEP_SERIAL if connection_type == TYPE_SERIAL else STEP_TCP

        errors: dict[str, str] = {}
        if user_input is not None:
            merged = {**entry.data, **_flatten(connection_type, user_input)}

            relinking = False
            if _needs_relink(entry, merged):
                # A failed unload keeps the port held on the old settings, so
                # the probe could only clash: abort rather than mislead.
                if not await self.hass.config_entries.async_unload(entry.entry_id):
                    return self.async_abort(reason="reconfigure_unload_failed")
                relinking = True

            serial: str | None = None
            error_key: str | None = None
            try:
                serial, error_key = await _async_probe(self.hass, merged)
            finally:
                # A mismatch, probe error, or cancellation left the entry off
                # the bus: put it back. A match falls through to the reload.
                if relinking and serial != entry.unique_id:
                    await self.hass.config_entries.async_setup(entry.entry_id)

            if error_key:
                errors["base"] = error_key
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch(reason="serial_mismatch")
                return self.async_update_reload_and_abort(entry, data=merged)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or _sectioned(dict(entry.data))
            ),
            errors=errors,
        )


class NeoPoolOptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for NeoPool integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = probatio.Schema(
            {
                probatio.Optional(
                    CONF_USE_LIGHT,
                    default=options.get(CONF_USE_LIGHT, False),
                ): bool,
                probatio.Optional(
                    CONF_USE_COVER_SENSOR,
                    default=options.get(CONF_USE_COVER_SENSOR, False),
                ): bool,
                probatio.Optional(
                    CONF_USE_AUX1,
                    default=options.get(CONF_USE_AUX1, False),
                ): bool,
                probatio.Optional(
                    CONF_USE_AUX2,
                    default=options.get(CONF_USE_AUX2, False),
                ): bool,
                probatio.Optional(
                    CONF_USE_AUX3,
                    default=options.get(CONF_USE_AUX3, False),
                ): bool,
                probatio.Optional(
                    CONF_USE_AUX4,
                    default=options.get(CONF_USE_AUX4, False),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
