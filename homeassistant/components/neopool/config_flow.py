"""Config flow for the NeoPool integration."""

from collections.abc import Mapping
from typing import Any, override

from neopool_modbus import async_probe_serial_unit
from neopool_modbus.exceptions import NeoPoolModbusError, NeoPoolTimeoutError
from neopool_modbus.registers import DEFAULT_MODBUS_FRAMER
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_MODBUS_FRAMER,
    CONF_UNIT_ID,
    CONF_USE_AUX1,
    CONF_USE_AUX2,
    CONF_USE_AUX3,
    CONF_USE_AUX4,
    CONF_USE_COVER_SENSOR,
    CONF_USE_LIGHT,
    CURRENT_VERSION,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .coordinator import NeoPoolConfigEntry
from .helpers import build_modbus_params


async def _async_probe(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Probe a device using user-supplied connection parameters."""
    params = build_modbus_params(user_input)
    try:
        async with async_get_temporary_unit(
            hass, params, user_input[CONF_UNIT_ID]
        ) as unit:
            serial = await async_probe_serial_unit(unit)
    except HomeAssistantError, NeoPoolTimeoutError:
        return None, "cannot_connect"
    except NeoPoolModbusError:
        return None, "cannot_read_modbus"
    return serial, None


def _needs_relink(entry: ConfigEntry, data: Mapping[str, Any]) -> bool:
    """Whether probing these settings clashes with the connection in use.

    One connection is shared per endpoint and cannot serve two sets of line
    settings at once, so changing the line settings of the port an entry polls
    needs that entry off the bus before the new settings can be probed. An entry
    waiting to retry counts as being on the bus; unloading it cancels the retry.
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
        """Handle the initial step of the configuration flow."""
        data_schema = probatio.Schema(
            {
                probatio.Required(CONF_HOST): str,
                probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Coerce(
                    int
                ),
                probatio.Optional(
                    CONF_UNIT_ID, default=DEFAULT_UNIT_ID
                ): probatio.Coerce(int),
                probatio.Optional(
                    CONF_MODBUS_FRAMER,
                    default=DEFAULT_MODBUS_FRAMER,
                ): probatio.In(("tcp", "rtu")),
            }
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            serial, error_key = await _async_probe(self.hass, user_input)
            if error_key:
                errors[CONF_HOST] = error_key
            else:
                assert serial is not None
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()
        current = entry.data

        data_schema = probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=current[CONF_HOST]): str,
                probatio.Optional(
                    CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)
                ): probatio.Coerce(int),
                probatio.Optional(
                    CONF_UNIT_ID,
                    default=current.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
                ): probatio.Coerce(int),
                probatio.Optional(
                    CONF_MODBUS_FRAMER,
                    default=current.get(CONF_MODBUS_FRAMER, DEFAULT_MODBUS_FRAMER),
                ): probatio.In(("tcp", "rtu")),
            }
        )

        errors: dict[str, str] = {}
        if user_input is not None:
            merged = {**current, **user_input}

            relinking = False
            if _needs_relink(entry, merged):
                # A failed unload leaves the entry loaded; let the probe run.
                relinking = await self.hass.config_entries.async_unload(entry.entry_id)

            serial, error_key = await _async_probe(self.hass, merged)

            # A mismatch or probe error left the entry off the bus: put it back.
            # A match falls through to the reload below on the new settings.
            if relinking and serial != entry.unique_id:
                await self.hass.config_entries.async_setup(entry.entry_id)

            if error_key:
                errors[CONF_HOST] = error_key
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch(reason="serial_mismatch")
                return self.async_update_reload_and_abort(entry, data=merged)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema, user_input or current
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
