"""Base class for NYT Games entities."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NYTGamesCoordinator


class NYTGamesEntity(CoordinatorEntity[NYTGamesCoordinator]):
    """Defines a base NYT Games entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NYTGamesCoordinator) -> None:
        """Initialize a NYT Games entity."""
        super().__init__(coordinator)
        unique_id = coordinator.config_entry.unique_id
        assert unique_id is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="New York Times",
        )
