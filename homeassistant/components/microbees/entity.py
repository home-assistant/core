"""Base entity for microBees."""

from microBeesPy.microbees import Actuator, Bee, MicroBees

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
        act_id: int,
        bee_id: int,
        microbees: MicroBees,
    ) -> None:
        """Initialize the microBees entity."""
        super().__init__(coordinator)
        self.bee_id = bee_id
        self.act_id = act_id
        self.microbees = microbees
        self._attr_unique_id = f"{self.bee.id}_{self.act.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.bee.id)},
            manufacturer="microBees",
            name=self.bee.name,
            model=self.bee.prototypeName,
        )

    @property
    def available(self) -> bool:
        """Status of the bee."""
        return (
            super().available
            and f"bee_{self.bee_id}" in self.coordinator.data.bees
            and self.bee.active
        )

    @property
    def bee(self) -> Bee:
        """Return the updated bee."""
        return self.coordinator.data.bees[f"bee_{self.bee_id}"]

    @property
    def act(self) -> Actuator:
        """Return the updated act."""
        return self.coordinator.data.actuators[f"act_{self.act_id}"]
