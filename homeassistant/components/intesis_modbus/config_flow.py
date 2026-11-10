"""Config flow for the Intesis Modbus integration."""

from typing import TYPE_CHECKING, Any, override

from intesis_gw_modbus import (
    KNOWN_DEVICE_IDS,
    GatewayModel,
    TemperatureFormat,
    detect_temperature_format,
    model_for_device_id,
)
from modbus_connection import ModbusError, ModbusExceptionError, ModbusUnit
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
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

DEVICE_ID_REGISTER = 49
SETPOINT_REGISTER = 4
VANE_REGISTER = 3

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): probatio.All(
            NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)
            ),
            probatio.Coerce(int),
        ),
    }
)

STEP_TEMPERATURE_FORMAT_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_TEMPERATURE_FORMAT, default=TemperatureFormat.DECICELSIUS.value
        ): SelectSelector(
            SelectSelectorConfig(
                options=[fmt.value for fmt in TemperatureFormat],
                translation_key="temperature_format",
                mode=SelectSelectorMode.LIST,
            )
        ),
    }
)

STEP_FEATURES_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_HAS_VANE, default=True): BooleanSelector()}
)


async def _async_read_or_none(unit: ModbusUnit, address: int) -> int | None:
    """Read one holding register, or None if the gateway refuses the address."""
    try:
        [value] = await unit.read_holding_registers(address, 1)
    except ModbusExceptionError:
        return None
    return value


class IntesisModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Intesis Modbus config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}
        self._model: GatewayModel | None = None
        self._raw_vane: int | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the serial link, then probe the gateway behind it."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_DEVICE]}:{user_input[CONF_UNIT_ID]}"
            )
            self._abort_if_unique_id_configured()
            try:
                async with async_get_temporary_unit(
                    self.hass,
                    create_modbus_params(user_input),
                    user_input[CONF_UNIT_ID],
                ) as unit:
                    device_id = await _async_read_or_none(unit, DEVICE_ID_REGISTER)
                    raw_setpoint = await _async_read_or_none(unit, SETPOINT_REGISTER)
                    self._raw_vane = await _async_read_or_none(unit, VANE_REGISTER)
            except (ModbusError, HomeAssistantError) as err:
                errors["base"] = "cannot_connect"
                description_placeholders["error"] = str(err)
            else:
                if (brand := KNOWN_DEVICE_IDS.get(device_id or -1)) is not None:
                    return self.async_abort(
                        reason="unsupported_brand",
                        description_placeholders={"brand": brand},
                    )
                if (model := model_for_device_id(device_id or -1)) is None:
                    return self.async_abort(reason="unsupported_device")
                self._model = model
                self._data = {**user_input, CONF_MODEL: model.name}
                if (fmt := detect_temperature_format(raw_setpoint)) is None:
                    return await self.async_step_temperature_format()
                self._data[CONF_TEMPERATURE_FORMAT] = fmt.value
                return await self.async_step_features()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_temperature_format(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the DIP-switch temperature format when it cannot be detected."""
        if user_input is not None:
            self._data[CONF_TEMPERATURE_FORMAT] = user_input[CONF_TEMPERATURE_FORMAT]
            return await self.async_step_features()
        return self.async_show_form(
            step_id="temperature_format",
            data_schema=STEP_TEMPERATURE_FORMAT_DATA_SCHEMA,
        )

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm whether the unit has a vane.

        The gateway has no capability register for the vane, so the probe's
        reading of register 3 only pre-fills the answer.
        """
        if TYPE_CHECKING:
            assert self._model is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._model.name, data={**self._data, **user_input}
            )
        return self.async_show_form(
            step_id="features",
            data_schema=self.add_suggested_values_to_schema(
                STEP_FEATURES_DATA_SCHEMA,
                {CONF_HAS_VANE: self._raw_vane in self._model.brand.vane_positions},
            ),
        )
