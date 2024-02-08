"""Base entity for microBees."""

from microBeesPy.microbees import Actuator, Bee

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MicroBeesUpdateCoordinator


class MicroBeesEntity(CoordinatorEntity[MicroBeesUpdateCoordinator]):
    """Base class for microBees entities."""

    def __init__(
        self, coordinator: MicroBeesUpdateCoordinator, act: Actuator, bee: Bee
    ) -> None:
        """Initialize the microBees entity."""
        super().__init__(coordinator)
        self._attr_available = False
        self.bee_id = bee.id
        self.act_id = act.id

    @property
    def updated_bee(self) -> Bee:
        """Return the updated bee."""
        return self.coordinator.data.get(f"bee_{self.bee_id}")

    @property
    def updated_act(self) -> Actuator:
        """Return the updated act."""
        return self.coordinator.data.get(f"act_{self.act_id}")
