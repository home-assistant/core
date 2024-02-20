"""Base entity for microBees."""

from microBeesPy import Actuator, Bee

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
    ) -> None:
        """Initialize the microBees entity."""
        super().__init__(coordinator)
        self.bee_id = bee_id
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


class MicroBeesActuatorEntity(MicroBeesEntity):
    """Base class for microBees entities with actuator."""

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        bee_id: int,
        actuator_id: int,
    ) -> None:
        """Initialize the microBees entity."""
        super().__init__(coordinator, bee_id)
        self.actuator_id = actuator_id
        self._attr_unique_id = f"{bee_id}_{actuator_id}"

    @property
    def actuator(self) -> Actuator:
        """Return the actuator."""
        return self.coordinator.data.actuators[self.actuator_id]
