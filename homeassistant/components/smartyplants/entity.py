"""Shared base entity — this is where each sensor becomes an HA device."""

from typing import override

from pysmartyplants import Sensor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, MODEL, STALE_AFTER
from .coordinator import SmartyPlantsCoordinator


def is_stale(sensor: Sensor) -> bool:
    """Return True when the last reading is too old to describe the plant."""
    if sensor.last_data_received is None:
        return True
    return dt_util.utcnow() - sensor.last_data_received > STALE_AFTER


class SmartyPlantsEntity(CoordinatorEntity[SmartyPlantsCoordinator]):
    """Common device wiring for every SmartyPlants entity."""

    _attr_has_entity_name = True
    # Cleared by the entities that report on the sensor itself, which have to
    # keep answering once it goes offline.
    _requires_online = True

    def __init__(self, coordinator: SmartyPlantsCoordinator, sensor_id: str) -> None:
        """Bind this entity to one physical sensor."""
        super().__init__(coordinator)
        self._sensor_id = sensor_id

        sensor = self.sensor
        plant = sensor.plant

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=(plant.name if plant else None) or sensor.name or sensor.identifier,
            serial_number=sensor.identifier,
        )

    @property
    def sensor(self) -> Sensor:
        """Return this sensor's slice of the last update."""
        return self.coordinator.data[self._sensor_id]

    @property
    @override
    def available(self) -> bool:
        """Report unavailable once the sensor stops reporting."""
        if not super().available or self._sensor_id not in self.coordinator.data:
            return False
        return self.sensor.is_online or not self._requires_online
