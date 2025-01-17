"""The entity for the Youless integration."""

from collections.abc import Callable

from youless_api import YoulessAPI

from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import YouLessCoordinator


class YouLessEntity(CoordinatorEntity[YouLessCoordinator]):
    """Base entity for YouLess."""

    def __init__(
        self,
        coordinator: YouLessCoordinator,
        value_func: Callable[[YoulessAPI], float | None],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device = coordinator.device
        self.value_func = value_func

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.value_func(self.device)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.value_func(self.device) is not None
