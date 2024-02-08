"""Base entity for microBees."""

from .coordinator import MicroBeesUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from microBeesPy.microbees import Actuator, Bee, MicroBees, MicroBeesException

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
        return next(filter(lambda x: x.id == self.bee_id, self.coordinator.data))

    @property
    def updated_act(self) -> Actuator:
        """Return the updated act."""
        if self.act is None:
            return None
        return next(filter(lambda x: x.id == self.act_id, self.updated_bee.actuators))
