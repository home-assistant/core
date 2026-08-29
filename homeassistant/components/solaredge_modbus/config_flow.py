"""Config flow to configure the SolarEdge Modbus integration."""

from collections.abc import Mapping
from typing import Any, override

from solaredged import SolarEdge, SolarEdgeConnectionError, SolarEdgeError
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_BAUDRATE,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    SUBSYSTEM_COMMON,
    SUBSYSTEM_INVERTER,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .entity import inverter_name
from .helpers import create_modbus_params

SECTION_MORE_OPTIONS = "more_options"

# Almost every inverter answers on the factory-default device ID, so that
# setting is tucked away in a collapsed section.
MORE_OPTIONS = {
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
    )
}

STEP_TCP = vol.Schema(
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
        **MORE_OPTIONS,
    }
)

STEP_SERIAL = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.All(
            NumberSelector(
                NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Coerce(int),
        ),
        **MORE_OPTIONS,
    }
)


def _flatten(connection_type: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten the sectioned form input into config entry data."""
    data = {CONF_TYPE: connection_type, **user_input}
    data[CONF_UNIT_ID] = data.pop(SECTION_MORE_OPTIONS)[CONF_UNIT_ID]

    if connection_type == TYPE_TCP:
        # One connection is shared per host and port, so spelling matters.
        data[CONF_HOST] = data[CONF_HOST].lower()

    return data


def _needs_relink(entry: ConfigEntry, data: Mapping[str, Any]) -> bool:
    """Whether probing these settings clashes with the connection in use.

    Everything talking to one device shares a single connection, which cannot
    serve two different sets of line settings at once. Changing the baud rate
    of the port an entry is polling is the case that needs that entry out of
    the way before the new settings can be probed.

    An entry waiting to retry counts as being on the bus: the retry would set
    it up on its old settings while the probe runs on the new ones. Unloading
    it cancels that.
    """
    if entry.state not in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
        return False

    current = create_modbus_params(entry.data)
    new = create_modbus_params(data)

    return new.endpoint == current.endpoint and new != current


def _sectioned(data: Mapping[str, Any]) -> dict[str, Any]:
    """Shape config entry data back into the sectioned form input."""
    return {
        **{key: value for key, value in data.items() if key != CONF_UNIT_ID},
        SECTION_MORE_OPTIONS: {CONF_UNIT_ID: data[CONF_UNIT_ID]},
    }


def _discovered_unit_id(discovery_info: ZeroconfServiceInfo) -> int:
    """Read the Modbus device ID out of the announcement.

    SolarEdge puts it in a MODBUS_ID TXT record. Anything unusable there falls
    back to the factory default, which is what the device would answer on.
    """
    try:
        unit_id = int(discovery_info.properties["MODBUS_ID"])
    except KeyError, TypeError, ValueError:
        return DEFAULT_UNIT_ID

    if not 1 <= unit_id <= 247:
        return DEFAULT_UNIT_ID

    return unit_id


class SolarEdgeModbusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a SolarEdge Modbus config flow."""

    VERSION = 1

    _discovered: dict[str, Any]
    _discovered_title: str

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle an inverter announcing itself over mDNS."""
        data = {
            CONF_TYPE: TYPE_TCP,
            CONF_HOST: discovery_info.host,
            CONF_PORT: discovery_info.port or DEFAULT_PORT,
            CONF_UNIT_ID: _discovered_unit_id(discovery_info),
        }

        # The announcement carries no serial number, and every identity here
        # derives from one, so the inverter has to be asked. An address is not
        # an identity: the one an entry is configured with can end up hosting
        # another inverter, and that one deserves to be offered.
        errors, solaredge = await self._async_validate(data)
        if solaredge is None:
            return self.async_abort(reason=errors["base"])

        await self.async_set_unique_id(solaredge.common.serial_number)
        # Keep up with a device that moved, but leave the device ID alone: the
        # user may be reaching it on one the announcement does not mention.
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: data[CONF_HOST], CONF_PORT: data[CONF_PORT]}
        )

        self._discovered = data
        self._discovered_title = inverter_name(solaredge.common.model)
        self.context["title_placeholders"] = {"name": self._discovered_title}

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setting up a discovered inverter."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_title, data=self._discovered
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._discovered_title,
                "host": self._discovered[CONF_HOST],
            },
        )

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
        return await self._async_step_link(TYPE_TCP, STEP_TCP, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an inverter reached over RS485."""
        return await self._async_step_link(TYPE_SERIAL, STEP_SERIAL, user_input)

    async def _async_step_link(
        self,
        connection_type: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the inverter behind them."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _flatten(connection_type, user_input)
            errors, solaredge = await self._async_validate(data)
            if solaredge is not None:
                await self.async_set_unique_id(solaredge.common.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=inverter_name(solaredge.common.model), data=data
                )

        return self.async_show_form(
            step_id=connection_type, data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of how the inverter is reached.

        The inverter may move to another address or device ID (a new gateway, a
        rewired RS485 bus), but it must stay the same inverter: the probed
        serial number has to match the entry's unique ID.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        connection_type = entry.data[CONF_TYPE]
        schema = STEP_SERIAL if connection_type == TYPE_SERIAL else STEP_TCP

        if user_input is not None:
            data = _flatten(connection_type, user_input)

            relinking = False
            if _needs_relink(entry, data):
                # A failed unload leaves the entry loaded; leave it be then and
                # let the probe report whatever it runs into.
                relinking = await self.hass.config_entries.async_unload(entry.entry_id)

            errors, solaredge = await self._async_validate(data)

            if solaredge is not None:
                await self.async_set_unique_id(solaredge.common.serial_number)

            # Anything other than the inverter this entry is for leaves it off
            # the bus, so put it back before reporting what happened. A match
            # falls through: the reload below brings it up on the new settings.
            if relinking and self.unique_id != entry.unique_id:
                await self.hass.config_entries.async_setup(entry.entry_id)

            if solaredge is not None:
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or _sectioned(entry.data)
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
                report = await solaredge.async_update()
        except HomeAssistantError, SolarEdgeConnectionError:
            # HomeAssistantError: the device is already in use over different
            # link settings, which one connection cannot honour.
            return {"base": "cannot_connect"}, None
        except SolarEdgeError:
            return {"base": "no_solaredge_device"}, None

        if solaredge.is_ev_charger:
            return {"base": "ev_charger"}, None

        # Setup needs both blocks, so a partial answer here would only create
        # an entry that cannot start.
        if {SUBSYSTEM_COMMON, SUBSYSTEM_INVERTER} & report.failed.keys():
            return {"base": "cannot_connect"}, None

        if not solaredge.common.serial_number:
            return {"base": "no_serial_number"}, None

        return {}, solaredge
