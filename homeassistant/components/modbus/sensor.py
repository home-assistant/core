"""Support for Modbus Register sensors."""
from __future__ import annotations

import logging
import struct
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_COUNT,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SENSORS,
    CONF_STRUCTURE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .base_platform import BasePlatform
from .const import (
    CONF_DATA_TYPE,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    DATA_TYPE_STRING,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up the Modbus sensors."""
    sensors = []

    if discovery_info is None:  # pragma: no cover
        return

    for entry in discovery_info[CONF_SENSORS]:
        hub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        sensors.append(ModbusRegisterSensor(hub, entry))

    async_add_entities(sensors)


class ModbusRegisterSensor(BasePlatform, RestoreEntity, SensorEntity):
    """Modbus register sensor."""

    def __init__(
        self,
        hub: ModbusHub,
        entry: dict[str, Any],
    ) -> None:
        """Initialize the modbus register sensor."""
        super().__init__(hub, entry)
        self._unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        self._count = int(entry[CONF_COUNT])
        self._swap = entry[CONF_SWAP]
        self._scale = entry[CONF_SCALE]
        self._offset = entry[CONF_OFFSET]
        self._precision = entry[CONF_PRECISION]
        self._structure = entry.get(CONF_STRUCTURE)
        self._data_type = entry[CONF_DATA_TYPE]

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._value = state.state

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def _swap_registers(self, registers):
        """Do swap as needed."""
        if self._swap in [CONF_SWAP_BYTE, CONF_SWAP_WORD_BYTE]:
            # convert [12][34] --> [21][43]
            for i, register in enumerate(registers):
                registers[i] = int.from_bytes(
                    register.to_bytes(2, byteorder="little"),
                    byteorder="big",
                    signed=False,
                )
        if self._swap in [CONF_SWAP_WORD, CONF_SWAP_WORD_BYTE]:
            # convert [12][34] ==> [34][12]
            registers.reverse()
        return registers

    async def async_update(self, now=None):
        """Update the state of the sensor."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        result = await self._hub.async_pymodbus_call(
            self._slave, self._address, self._count, self._input_type
        )
        if result is None:
            self._available = False
            self.async_write_ha_state()
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
        self.async_write_ha_state()
