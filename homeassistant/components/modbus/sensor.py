"""Support for Modbus Register sensors."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    RestoreSensor,
    SensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_hub
from .base_platform import BaseStructPlatform
from .const import CONF_SLAVE_COUNT
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Modbus sensors."""

    if discovery_info is None:
        return

    sensors: list[ModbusRegisterSensor | SlaveSensor] = []
    hub = get_hub(hass, discovery_info[CONF_NAME])
    for entry in discovery_info[CONF_SENSORS]:
        slave_count = entry.get(CONF_SLAVE_COUNT, 0)
        sensor = ModbusRegisterSensor(hub, entry, slave_count)
        if slave_count > 0:
            sensors.extend(await sensor.async_setup_slaves(hass, slave_count, entry))
        sensors.append(sensor)
    async_add_entities(sensors)


class ModbusRegisterSensor(BaseStructPlatform, RestoreSensor, SensorEntity):
    """Modbus register sensor."""

    def __init__(
        self,
        hub: ModbusHub,
        entry: dict[str, Any],
        slave_count: int,
    ) -> None:
        """Initialize the modbus register sensor."""
        super().__init__(hub, entry)
        if slave_count:
            self._count = self._count * slave_count
        self._coordinator: DataUpdateCoordinator[list[int] | None] | None = None
        self._attr_native_unit_of_measurement = entry.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_state_class = entry.get(CONF_STATE_CLASS)

    async def async_setup_slaves(
        self, hass: HomeAssistant, slave_count: int, entry: dict[str, Any]
    ) -> list[SlaveSensor]:
        """Add slaves as needed (1 read for multiple sensors)."""

        # Add a dataCoordinator for each sensor that have slaves
        # this ensures that idx = bit position of value in result
        # polling is done with the base class
        name = self._attr_name if self._attr_name else "modbus_sensor"
        self._coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=name,
        )

        slaves: list[SlaveSensor] = []
        for idx in range(0, slave_count):
            slaves.append(SlaveSensor(self._coordinator, idx, entry))
        return slaves

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the state of the sensor."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        raw_result = await self._hub.async_pymodbus_call(
            self._slave, self._address, self._count, self._input_type
        )
        if raw_result is None:
            if self._lazy_errors:
                self._lazy_errors -= 1
                return
            self._lazy_errors = self._lazy_error_count
            self._attr_available = False
            self._attr_native_value = None
            if self._coordinator:
                self._coordinator.async_set_updated_data(None)
            self.async_write_ha_state()
            return

        result = self.unpack_structure_result(raw_result.registers)
        if self._coordinator:
            if result:
                result_array = list(
                    map(float if self._precision else int, result.split(","))
                )
                self._attr_native_value = result_array[0]
                self._coordinator.async_set_updated_data(result_array)
            else:
                self._attr_native_value = None
                self._coordinator.async_set_updated_data(None)
        else:
            self._attr_native_value = result
        self._attr_available = self._attr_native_value is not None
        self._lazy_errors = self._lazy_error_count
        self.async_write_ha_state()


class SlaveSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[int] | None]],
    RestoreSensor,
    SensorEntity,
):
    """Modbus slave register sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[int] | None],
        idx: int,
        entry: dict[str, Any],
    ) -> None:
        """Initialize the Modbus register sensor."""
        idx += 1
        self._idx = idx
        self._attr_name = f"{entry[CONF_NAME]} {idx}"
        self._attr_unique_id = entry.get(CONF_UNIQUE_ID)
        if self._attr_unique_id:
            self._attr_unique_id = f"{self._attr_unique_id}_{idx}"
        self._attr_available = False
        super().__init__(coordinator)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        if state := await self.async_get_last_state():
            self._attr_native_value = state.state
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        result = self.coordinator.data
        self._attr_native_value = result[self._idx] if result else None
        super()._handle_coordinator_update()
