"""Base entity for the Nextcloud integration."""
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator


class NextcloudEntity(CoordinatorEntity[NextcloudDataUpdateCoordinator]):
    """Base Nextcloud entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextcloudDataUpdateCoordinator,
        item: str,
        entry: ConfigEntry,
        desc: EntityDescription | None,
    ) -> None:
        """Initialize the Nextcloud sensor."""
        super().__init__(coordinator)
        domain = urlparse(coordinator.url).netloc
        self.item = item
        self._attr_translation_key = slugify(item)
        self._attr_name = item
        self._attr_unique_id = f"{coordinator.url}#{item}"
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.url + "/settings/admin/serverinfo",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Nextcloud",
            name=domain,
            sw_version=coordinator.data.get("system version"),
        )
        self.entity_description = desc
