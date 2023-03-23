"""Base entity for the Nextcloud integration."""


from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NextcloudDataUpdateCoordinator


class NextcloudEntity(CoordinatorEntity[NextcloudDataUpdateCoordinator]):
    """Base Nextcloud entity."""

    _attr_icon = "mdi:cloud"

    def __init__(self, coordinator: NextcloudDataUpdateCoordinator, item: str) -> None:
        """Initialize the Nextcloud sensor."""
        super().__init__(coordinator)
        self.item = item
        self._attr_name = item

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.url}#{self.item}"
