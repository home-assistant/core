"""Support for Modbus Register sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
import struct

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import number
from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_DATA_TYPE,
    CONF_HUB,
    CONF_INPUT_TYPE,
    CONF_PRECISION,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_REVERSE_ORDER,
    CONF_SCALE,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_NONE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORDBYTE,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STRUCT_FORMAT,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_REGISTERS): [
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_REGISTER): cv.positive_int,
                vol.Optional(CONF_COUNT, default=1): cv.positive_int,
                vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_INT): vol.In(
                    [
                        DATA_TYPE_INT,
                        DATA_TYPE_UINT,
                        DATA_TYPE_FLOAT,
                        DATA_TYPE_STRING,
                        DATA_TYPE_CUSTOM,
                    ]
                ),
                vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
                vol.Optional(CONF_OFFSET, default=0): number,
                vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
                vol.Optional(
                    CONF_REGISTER_TYPE, default=CALL_TYPE_REGISTER_HOLDING
                ): vol.In([CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]),
                vol.Optional(CONF_REVERSE_ORDER, default=False): cv.boolean,
                vol.Optional(CONF_SCALE, default=1): number,
                vol.Optional(CONF_SLAVE): cv.positive_int,
                vol.Optional(CONF_STRUCTURE): cv.string,
                vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            }
        ]
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up the Modbus sensors."""
    sensors = []

    #  check for old config:
    if discovery_info is None:
        _LOGGER.warning(
            "Sensor configuration is deprecated, will be removed in a future release"
        )
        discovery_info = {
            CONF_NAME: "no name",
            CONF_SENSORS: config[CONF_REGISTERS],
        }
        for entry in discovery_info[CONF_SENSORS]:
            entry[CONF_ADDRESS] = entry[CONF_REGISTER]
            entry[CONF_INPUT_TYPE] = entry[CONF_REGISTER_TYPE]
            del entry[CONF_REGISTER]
            del entry[CONF_REGISTER_TYPE]
        config = None

    for entry in discovery_info[CONF_SENSORS]:
        if entry[CONF_DATA_TYPE] == DATA_TYPE_STRING:
            structure = str(entry[CONF_COUNT] * 2) + "s"
        elif entry[CONF_DATA_TYPE] != DATA_TYPE_CUSTOM:
            try:
                structure = f">{DEFAULT_STRUCT_FORMAT[entry[CONF_DATA_TYPE]][entry[CONF_COUNT]]}"
            except KeyError:
                _LOGGER.error(
                    "Unable to detect data type for %s sensor, try a custom type",
                    entry[CONF_NAME],
                )
                continue
        else:
            structure = entry.get(CONF_STRUCTURE)

        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            _LOGGER.error("Error in sensor %s structure: %s", entry[CONF_NAME], err)
            continue

        if entry[CONF_COUNT] * 2 != size:
            _LOGGER.error(
                "Structure size (%d bytes) mismatch registers count (%d words)",
                size,
                entry[CONF_COUNT],
            )
            continue

        if CONF_REVERSE_ORDER in entry:
            if entry[CONF_REVERSE_ORDER]:
                entry[CONF_SWAP] = CONF_SWAP_WORD
            else:
                entry[CONF_SWAP] = CONF_SWAP_NONE
            del entry[CONF_REVERSE_ORDER]
        if entry.get(CONF_SWAP) != CONF_SWAP_NONE:
            if entry[CONF_SWAP] == CONF_SWAP_BYTE:
                regs_needed = 1
            else:  # CONF_SWAP_WORDBYTE, CONF_SWAP_WORD
                regs_needed = 2
            if (
                entry[CONF_COUNT] < regs_needed
                or (entry[CONF_COUNT] % regs_needed) != 0
            ):
                _LOGGER.error(
                    "Error in sensor %s swap(%s) not possible due to count: %d",
                    entry[CONF_NAME],
                    entry[CONF_SWAP],
                    entry[CONF_COUNT],
                )
                continue
        if CONF_HUB in entry:
            # from old config!
            hub: ModbusHub = hass.data[MODBUS_DOMAIN][entry[CONF_HUB]]
        else:
            hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        if CONF_SCAN_INTERVAL not in entry:
            entry[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        sensors.append(
            ModbusRegisterSensor(
                hub,
                entry,
                structure,
            )
        )

    if not sensors:
        return
    async_add_entities(sensors)


class ModbusRegisterSensor(RestoreEntity, SensorEntity):
    """Modbus register sensor."""

    def __init__(
        self,
        hub,
        entry,
        structure,
    ):
        """Initialize the modbus register sensor."""
        self._hub = hub
        self._name = entry[CONF_NAME]
        slave = entry.get(CONF_SLAVE)
        self._slave = int(slave) if slave else None
        self._register = int(entry[CONF_ADDRESS])
        self._register_type = entry[CONF_INPUT_TYPE]
        self._unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        self._count = int(entry[CONF_COUNT])
        self._swap = entry[CONF_SWAP]
        self._scale = entry[CONF_SCALE]
        self._offset = entry[CONF_OFFSET]
        self._precision = entry[CONF_PRECISION]
        self._structure = structure
        self._data_type = entry[CONF_DATA_TYPE]
        self._device_class = entry.get(CONF_DEVICE_CLASS)
        self._value = None
        self._available = True
        self._scan_interval = timedelta(seconds=entry.get(CONF_SCAN_INTERVAL))

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if state:
            self._value = state.state

        async_track_time_interval(
            self.hass, lambda arg: self._update(), self._scan_interval
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """

        # Handle polling directly in this entity
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def _swap_registers(self, registers):
        """Do swap as needed."""
        if self._swap in [CONF_SWAP_BYTE, CONF_SWAP_WORDBYTE]:
            # convert [12][34] --> [21][43]
            for i, register in enumerate(registers):
                registers[i] = int.from_bytes(
                    register.to_bytes(2, byteorder="little"),
                    byteorder="big",
                    signed=False,
                )
        if self._swap in [CONF_SWAP_WORD, CONF_SWAP_WORDBYTE]:
            # convert [12][34] ==> [34][12]
            registers.reverse()
        return registers

    def _update(self):
        """Update the state of the sensor."""
        if self._register_type == CALL_TYPE_REGISTER_INPUT:
            result = self._hub.read_input_registers(
                self._slave, self._register, self._count
            )
        else:
            result = self._hub.read_holding_registers(
                self._slave, self._register, self._count
            )
        if result is None:
            self._available = False
            self.schedule_update_ha_state()
            return

        registers = self._swap_registers(result.registers)
        byte_string = b"".join([x.to_bytes(2, byteorder="big") for x in registers])
        if self._data_type == DATA_TYPE_STRING:
            self._value = byte_string.decode()
        else:
            val = struct.unpack(self._structure, byte_string)

            # Issue: https://github.com/home-assistant/core/issues/41944
            # If unpack() returns a tuple greater than 1, don't try to process the value.
            # Instead, return the values of unpack(...) separated by commas.
            if len(val) > 1:
                # Apply scale and precision to floats and ints
                v_result = []
                for entry in val:
                    v_temp = self._scale * entry + self._offset

                    # We could convert int to float, and the code would still work; however
                    # we lose some precision, and unit tests will fail. Therefore, we do
                    # the conversion only when it's absolutely necessary.
                    if isinstance(v_temp, int) and self._precision == 0:
                        v_result.append(str(v_temp))
                    else:
                        v_result.append(f"{float(v_temp):.{self._precision}f}")
                self._value = ",".join(map(str, v_result))
            else:
                # Apply scale and precision to floats and ints
                val = self._scale * val[0] + self._offset

                # We could convert int to float, and the code would still work; however
                # we lose some precision, and unit tests will fail. Therefore, we do
                # the conversion only when it's absolutely necessary.
                if isinstance(val, int) and self._precision == 0:
                    self._value = str(val)
                else:
                    self._value = f"{float(val):.{self._precision}f}"

        self._available = True
        self.schedule_update_ha_state()
