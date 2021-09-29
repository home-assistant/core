"""Support for Modbus Register sensors."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorEntity
from homeassistant.const import CONF_NAME, CONF_SENSORS, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .base_platform import BaseStructPlatform
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Modbus sensors."""
    sensors = []

    if discovery_info is None:  # pragma: no cover
        return

    for entry in discovery_info[CONF_SENSORS]:
        hub = get_hub(hass, discovery_info[CONF_NAME])
        sensors.append(ModbusRegisterSensor(hub, entry))

    async_add_entities(sensors)


class ModbusRegisterSensor(BaseStructPlatform, RestoreEntity, SensorEntity):
    """Modbus register sensor."""

    def __init__(
        self,
        hub: ModbusHub,
        entry: dict[str, Any],
    ) -> None:
        """Initialize the modbus register sensor."""
        super().__init__(hub, entry)
        self._attr_native_unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_state_class = entry.get(CONF_STATE_CLASS)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._attr_native_value = state.state

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the state of the sensor."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        result = await self._hub.async_pymodbus_call(
            self._slave, self._address, self._count, self._input_type
        )
        if result is None:
            if self._lazy_errors:
                self._lazy_errors -= 1
                return
            self._lazy_errors = self._lazy_error_count
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_native_value = self.unpack_structure_result(result.registers)
        self._lazy_errors = self._lazy_error_count
        self._attr_available = True
        self.async_write_ha_state()
