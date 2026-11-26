"""Config flow for the Intesis Modbus integration."""

import asyncio
from typing import TYPE_CHECKING, Any, override

from intesis_gw_modbus import GatewayModel, GatewayProbe, async_probe_gateway
from modbus_connection import ModbusError
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
)

from .const import (
    CONF_BAUDRATE,
    CONF_HAS_VANE,
    CONF_MODEL,
    CONF_TEMPERATURE_FORMAT,
    CONF_UNIT_ID,
    DOMAIN,
)
from .helpers import create_modbus_params

DEFAULT_BAUDRATE = 9600
DEFAULT_UNIT_ID = 1

_BAUDRATE = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
    probatio.Coerce(int),
)
_UNIT_ID = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): _BAUDRATE,
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): _UNIT_ID,
    }
)

STEP_FEATURES_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_HAS_VANE, default=True): BooleanSelector()}
)


def _entry_data(user_input: dict[str, Any], probe: GatewayProbe) -> dict[str, Any]:
    """The entry data for a gateway that identified itself and reports values."""
    if TYPE_CHECKING:
        assert probe.model is not None
        assert probe.temperature_format is not None
    return {
        **user_input,
        CONF_MODEL: probe.model.name,
        CONF_TEMPERATURE_FORMAT: probe.temperature_format.value,
    }


class IntesisModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Intesis Modbus config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}
        self._model: GatewayModel | None = None
        self._vane_reported = False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the serial link, then probe the gateway behind it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_DEVICE: user_input[CONF_DEVICE],
                    CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                }
            )
            errors, probe = await self._async_validate(user_input)
            if probe is not None:
                self._model = probe.model
                self._vane_reported = probe.vane_reported
                self._data = _entry_data(user_input, probe)
                return await self.async_step_features()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at the serial link the gateway moved to."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, result = await self._async_reconfigure(
                reconfigure_entry, user_input
            )
            if result is not None:
                return result

        # A field left out keeps what the entry has, not the factory default
        data = reconfigure_entry.data
        schema = STEP_USER_DATA_SCHEMA.extend(
            {
                probatio.Required(
                    CONF_BAUDRATE, default=data[CONF_BAUDRATE]
                ): _BAUDRATE,
                probatio.Required(CONF_UNIT_ID, default=data[CONF_UNIT_ID]): _UNIT_ID,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or data),
            errors=errors,
        )

    async def _async_reconfigure(
        self, entry: ConfigEntry, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], ConfigFlowResult | None]:
        """Probe the new link and save it, returning form errors otherwise."""
        match = {
            CONF_DEVICE: user_input[CONF_DEVICE],
            CONF_UNIT_ID: user_input[CONF_UNIT_ID],
        }
        self._async_abort_entries_match(match)
        # A loaded entry holds its port at the old baud rate, which refuses a
        # probe at another one, so it lets go of the port meanwhile.
        unload: asyncio.Task[bool] | None = None
        if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
            current = create_modbus_params(entry.data)
            new = create_modbus_params(user_input)
            if new.endpoint == current.endpoint and new != current:
                unload = self.hass.async_create_task(
                    self.hass.config_entries.async_unload(entry.entry_id),
                    f"{DOMAIN} unload {entry.entry_id}",
                )
        restore = unload is not None
        try:
            try:
                if unload is not None and not await asyncio.shield(unload):
                    # The port is still held, so the probe could only fail
                    raise AbortFlow("unload_failed")
                errors, probe = await self._async_validate(user_input)
            except asyncio.CancelledError:
                # The request is gone and cannot wait: the way back runs alone
                if unload is not None:
                    self._async_restore(entry, unload)
                restore = False
                raise
            if probe is not None:
                # Another flow may have claimed the gateway meanwhile, and this
                # one may have been removed: the lookup raises for a flow gone.
                self._async_abort_entries_match(match)
                self.hass.config_entries.flow.async_get(self.flow_id)
                restore = False
                return {}, self.async_update_reload_and_abort(
                    entry, data_updates=_entry_data(user_input, probe)
                )
        finally:
            if restore and unload is not None:
                await asyncio.shield(self._async_restore(entry, unload))
        return errors, None

    @callback
    def _async_restore(
        self, entry: ConfigEntry, unload: asyncio.Task[bool]
    ) -> asyncio.Task[None]:
        """Load an entry again that was unloaded for a probe."""

        async def _restore() -> None:
            if await unload:
                await self.hass.config_entries.async_reload(entry.entry_id)

        return self.hass.async_create_task(
            _restore(), f"{DOMAIN} restore {entry.entry_id}"
        )

    async def _async_validate(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], GatewayProbe | None]:
        """Probe the gateway, returning form errors or what it answered.

        The probe is ``None`` only alongside a non-empty errors dict.
        """
        try:
            async with async_get_temporary_unit(
                self.hass,
                create_modbus_params(user_input),
                user_input[CONF_UNIT_ID],
            ) as unit:
                probe = await async_probe_gateway(unit)
        except HomeAssistantError:
            return {"base": "device_in_use"}, None
        except ModbusError:
            return {"base": "cannot_connect"}, None
        if probe.unsupported_brand is not None:
            raise AbortFlow(
                "unsupported_brand",
                description_placeholders={"brand": probe.unsupported_brand},
            )
        if probe.model is None:
            return {"base": "unsupported_device"}, None
        if probe.temperature_format is None:
            return {"base": "gateway_starting"}, None
        return {}, probe

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm whether the unit has a vane.

        The gateway has no capability register for the vane, so the probe's
        hint only pre-fills the answer.
        """
        if TYPE_CHECKING:
            assert self._model is not None
        if user_input is not None:
            # Another flow for the same gateway may have finished meanwhile
            self._async_abort_entries_match(
                {
                    CONF_DEVICE: self._data[CONF_DEVICE],
                    CONF_UNIT_ID: self._data[CONF_UNIT_ID],
                }
            )
            return self.async_create_entry(
                title=self._model.name, data=self._data, options=user_input
            )
        return self.async_show_form(
            step_id="features",
            data_schema=self.add_suggested_values_to_schema(
                STEP_FEATURES_DATA_SCHEMA,
                {CONF_HAS_VANE: self._vane_reported},
            ),
        )
