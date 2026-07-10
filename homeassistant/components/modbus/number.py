"""Support for Modbus Numbers."""

import struct
from typing import Any, override

from homeassistant.components.number import NumberEntity, RestoreNumber
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OFFSET,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .const import (
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_NUMBER_STEP,
    CONF_NUMBERS,
    CONF_SCALE,
    DEFAULT_OFFSET,
    DEFAULT_SCALE,
)
from .entity import ModbusStructEntity
from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Modbus numbers."""
    if discovery_info is None:
        return

    hub = get_hub(hass, discovery_info[CONF_NAME])
    async_add_entities(
        ModbusNumber(hass, hub, entry) for entry in discovery_info[CONF_NUMBERS]
    )


class ModbusNumber(ModbusStructEntity, RestoreNumber, NumberEntity):
    """Modbus number entity, reads and writes a numeric value stored in one or more holding registers."""

    def __init__(
        self, hass: HomeAssistant, hub: ModbusHub, entry: dict[str, Any]
    ) -> None:
        """Initialize the modbus number entity."""
        super().__init__(hass, hub, entry)
        self._scale = entry.get(CONF_SCALE, DEFAULT_SCALE)
        self._offset = entry.get(CONF_OFFSET, DEFAULT_OFFSET)
        self._attr_native_unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_device_class = entry.get(CONF_DEVICE_CLASS)
        self._attr_native_min_value = entry[CONF_MIN_VALUE]
        self._attr_native_max_value = entry[CONF_MAX_VALUE]
        self._attr_native_step = entry[CONF_NUMBER_STEP]
        # Without this, min/max from config would alter the value read from Modbus (sensor behavior).
        # Number entities use min/max only to limit what the user can set in the UI.
        self._min_value = None
        self._max_value = None

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if (data := await self.async_get_last_number_data()) is not None:
            self._attr_native_value = data.native_value

    @override
    async def _async_update(self) -> None:
        """Update the state of the number entity."""
        raw_result = await self._hub.async_pb_call(
            self._device_address, self._address, self._count, self._input_type
        )
        if raw_result is None:
            self._attr_available = False
            self._attr_native_value = None
            return
        self._attr_available = True
        result = self.unpack_structure_result(
            raw_result.registers, self._scale, self._offset
        )
        if result is None:
            self._attr_native_value = None
        elif self._precision == 0:
            self._attr_native_value = int(result)
        else:
            self._attr_native_value = float(result)

    def _convert_to_registers(
        self, value: float, scale: float, offset: float
    ) -> list[int]:
        """Convert a value to a list of registers, honoring structure and swap settings."""
        raw: float | int = (value - offset) / scale
        if self._value_is_int:
            raw = round(raw)
        as_bytes = struct.pack(self._structure, raw)
        raw_regs = [
            int.from_bytes(as_bytes[i : i + 2], "big")
            for i in range(0, len(as_bytes), 2)
        ]
        return self._swap_registers(raw_regs, 0)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value via Modbus."""
        registers = self._convert_to_registers(value, self._scale, self._offset)
        if len(registers) == 1:
            result = await self._hub.async_pb_call(
                self._device_address,
                self._address,
                registers[0],
                CALL_TYPE_WRITE_REGISTER,
            )
        else:
            result = await self._hub.async_pb_call(
                self._device_address,
                self._address,
                registers,
                CALL_TYPE_WRITE_REGISTERS,
            )
        if result is None:
            self._attr_available = False
            self.async_write_ha_state()
            return
        await self.async_local_update(cancel_pending_update=True)
