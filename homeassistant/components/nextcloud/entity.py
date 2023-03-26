"""Base entity for the Nextcloud integration."""


from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            name=self.coordinator.url,
            identifiers={(DOMAIN, self.coordinator.url)},
            model="Nextcloud",
            sw_version=self.coordinator.data.get("nextcloud_system_version"),
            configuration_url=self.coordinator.url,
        )
