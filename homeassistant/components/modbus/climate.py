"""Support for Generic Modbus Thermostats."""
from datetime import timedelta
import logging
import struct
from typing import Any, Dict, Optional

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from . import ModbusHub
from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_CLIMATES,
    CONF_CURRENT_TEMP,
    CONF_CURRENT_TEMP_REGISTER_TYPE,
    CONF_DATA_COUNT,
    CONF_DATA_TYPE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_OFFSET,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_STEP,
    CONF_TARGET_TEMP,
    CONF_UNIT,
    DATA_TYPE_CUSTOM,
    DEFAULT_STRUCT_FORMAT,
    MODBUS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities,
    discovery_info: Optional[DiscoveryInfoType] = None,
):
    """Read configuration and create Modbus climate."""
    if discovery_info is None:
        return

    entities = []
    for entity in discovery_info[CONF_CLIMATES]:
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        count = entity[CONF_DATA_COUNT]
        data_type = entity[CONF_DATA_TYPE]
        name = entity[CONF_NAME]
        structure = entity[CONF_STRUCTURE]

        if data_type != DATA_TYPE_CUSTOM:
            try:
                structure = f">{DEFAULT_STRUCT_FORMAT[data_type][count]}"
            except KeyError:
                _LOGGER.error(
                    "Climate %s: Unable to find a data type matching count value %s, try a custom type",
                    name,
                    count,
                )
                continue

        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            _LOGGER.error("Error in sensor %s structure: %s", name, err)
            continue

        if count * 2 != size:
            _LOGGER.error(
                "Structure size (%d bytes) mismatch registers count (%d words)",
                size,
                count,
            )
            continue

        entity[CONF_STRUCTURE] = structure
        entities.append(ModbusThermostat(hub, entity))

    async_add_entities(entities)


class ModbusThermostat(ClimateEntity):
    """Representation of a Modbus Thermostat."""

    def __init__(
        self,
        hub: ModbusHub,
        config: Dict[str, Any],
    ):
        """Initialize the modbus thermostat."""
        self._hub: ModbusHub = hub
        self._name = config[CONF_NAME]
        self._slave = config[CONF_SLAVE]
        self._target_temperature_register = config[CONF_TARGET_TEMP]
        self._current_temperature_register = config[CONF_CURRENT_TEMP]
        self._current_temperature_register_type = config[
            CONF_CURRENT_TEMP_REGISTER_TYPE
        ]
        self._target_temperature = None
        self._current_temperature = None
        self._data_type = config[CONF_DATA_TYPE]
        self._structure = config[CONF_STRUCTURE]
        self._count = config[CONF_DATA_COUNT]
        self._precision = config[CONF_PRECISION]
        self._scale = config[CONF_SCALE]
        self._scan_interval = timedelta(seconds=config[CONF_SCAN_INTERVAL])
        self._offset = config[CONF_OFFSET]
        self._unit = config[CONF_UNIT]
        self._max_temp = config[CONF_MAX_TEMP]
        self._min_temp = config[CONF_MIN_TEMP]
        self._temp_step = config[CONF_STEP]
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_track_time_interval(
            self.hass, lambda arg: self._update(), self._scan_interval
        )

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """

        # Handle polling directly in this entity
        return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the possible HVAC modes."""
        return [HVAC_MODE_AUTO]

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        # Home Assistant expects this method.
        # We'll keep it here to avoid getting exceptions.

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT if self._unit == "F" else TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._temp_step

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = int(
            (kwargs.get(ATTR_TEMPERATURE) - self._offset) / self._scale
        )
        if target_temperature is None:
            return
        byte_string = struct.pack(self._structure, target_temperature)
        register_value = struct.unpack(">h", byte_string[0:2])[0]
        self._write_register(self._target_temperature_register, register_value)
        self._update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def _update(self):
        """Update Target & Current Temperature."""
        self._target_temperature = self._read_register(
            CALL_TYPE_REGISTER_HOLDING, self._target_temperature_register
        )
        self._current_temperature = self._read_register(
            self._current_temperature_register_type, self._current_temperature_register
        )

        self.schedule_update_ha_state()

    def _read_register(self, register_type, register) -> Optional[float]:
        """Read register using the Modbus hub slave."""
        try:
            if register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(
                    self._slave, register, self._count
                )
            else:
                result = self._hub.read_holding_registers(
                    self._slave, register, self._count
                )
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        byte_string = b"".join(
            [x.to_bytes(2, byteorder="big") for x in result.registers]
        )
        val = struct.unpack(self._structure, byte_string)[0]
        register_value = format(
            (self._scale * val) + self._offset, f".{self._precision}f"
        )
        register_value = float(register_value)
        self._available = True

        return register_value

    def _write_register(self, register, value):
        """Write holding register using the Modbus hub slave."""
        try:
            self._hub.write_registers(self._slave, register, [value, 0])
        except ConnectionException:
            self._available = False
            return

        self._available = True
