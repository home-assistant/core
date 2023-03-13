"""Entity for the Nextcloud integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NextcloudDataUpdateCoordinator


class NextcloudEntity(CoordinatorEntity[NextcloudDataUpdateCoordinator]):
    """Basis Nextcloud entity."""

    def __init__(self, coordinator, item) -> None:
        """Initialize the Nextcloud sensor."""
        super().__init__(coordinator)
        self.item = item
        self._attr_name = item
        self._attr_icon = "mdi:cloud"

    @property
    def data(self) -> dict:
        """Return Nextcloud data."""
        return self.coordinator.data

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.url}#{self.item}"
