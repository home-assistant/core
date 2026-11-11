"""Config flow for Zehnder ComfoConnect PRO gateways."""

from collections.abc import Mapping
import logging
from typing import Any, override

from comfoconnect_pro_modbus import (
    ComfoConnectPro,
    ConnectionState,
    NoVentilationUnitError,
)
from modbus_connection import ModbusError, ModbusSerialParams, ModbusTcpParams
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
    TextSelector,
)

from .const import (
    BAUDRATES,
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    PARITIES,
    TYPE_SERIAL,
    TYPE_TCP,
)

_LOGGER = logging.getLogger(__name__)

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
        probatio.Required(CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)): probatio.All(
            SelectSelector(
                SelectSelectorConfig(
                    options=[str(baudrate) for baudrate in BAUDRATES],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_PARITY, default=DEFAULT_PARITY): SelectSelector(
            SelectSelectorConfig(
                options=list(PARITIES),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_PARITY,
            )
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        parity = PARITIES[data[CONF_PARITY]]
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            parity=parity,
            # The gateway takes 2 stop bits without parity and 1 with it.
            stopbits=2 if parity == "N" else 1,
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def _link_data(connection_type: str, user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Entry data for a form's input, with the host in one canonical spelling."""
    data = {CONF_TYPE: connection_type, **user_input}
    if CONF_HOST in data:
        # Fold the host's case, but keep an IPv6 scope ID such as %Eth0 as typed
        host, percent, scope = data[CONF_HOST].strip().partition("%")
        data[CONF_HOST] = host.lower() + percent + scope
    return data


def _link_identity(data: Mapping[str, Any]) -> dict[str, Any]:
    """The entry data that names the gateway's link, for duplicate checks.

    A TCP gateway may answer on any unit ID, so its identity leaves the ID out.
    """
    if data[CONF_TYPE] == TYPE_SERIAL:
        keys: tuple[str, ...] = (CONF_TYPE, CONF_DEVICE, CONF_UNIT_ID)
    else:
        keys = (CONF_TYPE, CONF_HOST, CONF_PORT)
    return {key: data[key] for key in keys}


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Connect to the gateway and check it reaches a ventilation unit, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        await ComfoConnectPro.async_detect(unit)


class ComfoConnectProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a ComfoConnect PRO config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the gateway is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a gateway reached over the network."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a gateway reached over RS-485."""
        return await self._async_step_link(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the gateway behind them."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = _link_data(connection_type, user_input)
            # The gateway has no serial number, so its link identifies it.
            self._async_abort_entries_match(_link_identity(data))
            errors, description_placeholders = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        return self.async_show_form(
            step_id=connection_type,
            data_schema=self.add_suggested_values_to_schema(
                schema, _suggested(user_input)
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Probe the gateway, returning the errors to show, if any."""
        try:
            await _async_probe(self.hass, data)
        except NoVentilationUnitError as err:
            # State OK means the gateway lost its path to the unit after reporting it
            if err.code is None or err.state is ConnectionState.OK:
                return {"base": "no_path_to_unit"}, {}
            return {"base": "no_ventilation_unit"}, {"state": str(err.code)}
        except (ModbusError, HomeAssistantError) as err:
            _LOGGER.debug("Could not reach the gateway: %r", err)
            return {"base": "cannot_connect"}, {}
        except Exception:
            _LOGGER.exception("Unexpected error while probing the gateway")
            return {"base": "unknown"}, {}
        return {}, {}


def _suggested(user_input: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Form input as suggested values, with the baud rate as its option."""
    if user_input is None:
        return None
    suggested = dict(user_input)
    if CONF_BAUDRATE in suggested:
        suggested[CONF_BAUDRATE] = str(suggested[CONF_BAUDRATE])
    return suggested
