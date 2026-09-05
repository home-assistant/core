"""Shared base entity — this is where each sensor becomes an HA device."""

from typing import override

from pysmartyplants import Sensor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SmartyPlantsCoordinator


class SmartyPlantsEntity(CoordinatorEntity[SmartyPlantsCoordinator]):
    """Common device wiring for every SmartyPlants entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmartyPlantsCoordinator, sensor_id: str) -> None:
        """Bind this entity to one physical sensor."""
        super().__init__(coordinator)
        self._sensor_id = sensor_id

        sensor = self.sensor
        plant = sensor.plant

        # Registering a device is what puts these entities on the auto-generated
        # dashboard and lets the user assign them to an area.
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
        return (
            super().available
            and self._sensor_id in self.coordinator.data
            and self.sensor.is_online
        )
