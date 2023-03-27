"""Base entity for the Nextcloud integration."""


from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator


class NextcloudEntity(CoordinatorEntity[NextcloudDataUpdateCoordinator]):
    """Base Nextcloud entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud"

    def __init__(
        self, coordinator: NextcloudDataUpdateCoordinator, item: str, entry: ConfigEntry
    ) -> None:
        """Initialize the Nextcloud sensor."""
        super().__init__(coordinator)
        self.item = item
        self.entry = entry
        self._attr_name = item

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.url}#{self.item}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            name="Nextcloud",
            identifiers={(DOMAIN, self.entry.entry_id)},
            model="Nextcloud",
            sw_version=self.coordinator.data.get("nextcloud_system_version"),
            configuration_url=self.coordinator.url,
        )
