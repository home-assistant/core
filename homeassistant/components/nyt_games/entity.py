"""Base class for NYTGames entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NYTGamesCoordinator


class NYTGamesEntity(CoordinatorEntity[NYTGamesCoordinator]):
    """Defines a base NYTGames entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NYTGamesCoordinator) -> None:
        """Initialize a NYT Games entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.config_entry.unique_id))},
            manufacturer="New York Times",
        )
