"""Base entity for microBees."""

from microBeesPy import Actuator, Bee, Sensor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator


class MicroBeesEntity(CoordinatorEntity[MicroBeesUpdateCoordinator]):
    """Base class for microBees entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        bee_id: int,
        actuator_id: int,
        sensor_id: int = 0,
    ) -> None:
        """Initialize the microBees entity."""
        super().__init__(coordinator)
        self.bee_id = bee_id
        self.actuator_id = actuator_id
        self.sensor_id = sensor_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(bee_id))},
            manufacturer="microBees",
            name=self.bee.name,
            model=self.bee.prototypeName,
        )

    @property
    def available(self) -> bool:
        """Status of the bee."""
        return (
            super().available
            and self.bee_id in self.coordinator.data.bees
            and self.bee.active
        )

    @property
    def bee(self) -> Bee:
        """Return the bee."""
        return self.coordinator.data.bees[self.bee_id]

    @property
    def actuator(self) -> Actuator:
        """Return the actuator."""
        if self.actuator_id is not None:
            return self.coordinator.data.actuators[self.actuator_id]

    @property
    def sensor(self) -> Sensor:
        """Return the sensor."""
        if self.sensor_id is not None:
            return self.coordinator.data.sensors[self.sensor_id]
