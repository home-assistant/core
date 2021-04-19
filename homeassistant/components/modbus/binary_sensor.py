"""Support for Modbus Coil and Discrete Input sensors."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .base_platform import BasePlatform
from .const import CONF_VIRTUAL_COUNT
from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Modbus binary sensors."""

    if discovery_info is None:  # pragma: no cover
        return

    sensors: list[ModbusBinarySensor | VirtualSensor] = []
    hub = get_hub(hass, discovery_info[CONF_NAME])
    for entry in discovery_info[CONF_BINARY_SENSORS]:
        virtuals = [
            VirtualSensor(i, entry) for i in range(1, entry[CONF_VIRTUAL_COUNT] + 1)
        ]
        sensors.append(ModbusBinarySensor(hub, entry, virtuals))
        sensors.extend(virtuals)
    async_add_entities(sensors)


class ModbusBinarySensor(BasePlatform, RestoreEntity, BinarySensorEntity):
    """Modbus binary sensor."""

    def __init__(
        self, hub: ModbusHub, entry: dict[str, Any], virtuals: list[VirtualSensor]
    ) -> None:
        """Initialize the Modbus binary sensor."""
        self._count = len(virtuals) + 1
        self._virtuals = virtuals
        super().__init__(hub, entry)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            self._attr_is_on = state.state == STATE_ON

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the state of the sensor."""

        # do not allow multiple active calls to the same platform
        if self._call_active:
            return
        self._call_active = True
        result = await self._hub.async_pymodbus_call(
            self._slave, self._address, self._count, self._input_type
        )
        self._call_active = False
        if result is None:
            if self._lazy_errors:
                self._lazy_errors -= 1
                return
            self._lazy_errors = self._lazy_error_count
            self._attr_available = False
            result_bits = None
        else:
            self._lazy_errors = self._lazy_error_count
            self._attr_is_on = result.bits[0] & 1
            self._attr_available = True
            result_bits = result.bits

        self.schedule_update_ha_state()
        self.async_write_ha_state()
        for entry in self._virtuals:
            entry.set_from_master(result_bits, self._attr_available)


class VirtualSensor(RestoreEntity, BinarySensorEntity):
    """Modbus virtual binary sensor."""

    def __init__(self, inx: int, entry: dict[str, Any]) -> None:
        """Initialize the Modbus binary sensor."""
        self._attr_name = f"{entry[CONF_NAME]}_{inx}"
        self._attr_device_class = entry.get(CONF_DEVICE_CLASS)
        self._attr_should_poll = False
        self._attr_available = False
        self._result_inx = int(inx / 8)
        self._result_bit = 2 ** (inx % 8)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        if state := await self.async_get_last_state():
            self._attr_is_on = state.state == STATE_ON
            self._attr_available = True
            self.async_write_ha_state()

    def set_from_master(self, bits: list[int] | None, available: bool) -> None:
        """Update the state of the sensor."""
        if bits is not None:
            self._attr_is_on = bits[self._result_inx] & self._result_bit
        self._attr_available = available
        self.schedule_update_ha_state()
