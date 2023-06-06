"""Base entity for the Nextcloud integration."""
from copy import copy
from urllib.parse import urlparse

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator

DIAGNOSTICS = ["apcu", "cache", "interned_strings", "jit", "opcache", "sma"]
ICONS = {
    "activeUsers": "mdi:account-multiple",
    "database": "mdi:database",
    "freespace": "mdi:harddisk",
    "mem_free": "mdi:memory",
    "mem_total": "mdi:memory",
    "php": "mdi:language-php",
    "swap_free": "mdi:memory",
    "swap_total": "mdi:memory",
    "update": "mdi:update",
}


class NextcloudEntity(CoordinatorEntity[NextcloudDataUpdateCoordinator]):
    """Base Nextcloud entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextcloudDataUpdateCoordinator,
        item: str,
        entry: ConfigEntry,
        desc: SensorEntityDescription | None,
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
        if desc:
            self.entity_description = copy(desc)
            self.entity_description.key = item
        else:
            self.entity_description = SensorEntityDescription(key=item)

        if any(x in item for x in DIAGNOSTICS):
            self.entity_description.entity_category = EntityCategory.DIAGNOSTIC
            self.entity_description.entity_registry_enabled_default = False

        icon = next(filter(lambda x: x in item, ICONS), None)
        if icon:
            self.entity_description.icon = ICONS[icon]
