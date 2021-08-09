"""Support for Modbus Register sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, CONF_SENSORS, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .base_platform import BaseStructPlatform
from .const import CONF_LAST_RESET
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
        self._attr_unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_last_reset = entry.get(CONF_LAST_RESET)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._attr_state = state.state

    async def async_update(self, now=None):
        """Update the state of the sensor."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        result = await self._hub.async_pymodbus_call(
            self._slave, self._address, self._count, self._input_type
        )
        if result is None:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_state = self.unpack_structure_result(result.registers)
        self._attr_available = True
        self.async_write_ha_state()
