"""Summary binary data from Nextcoud."""
from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

BINARY_SENSORS: Final[dict[str, BinarySensorEntityDescription]] = {
    "system_debug": BinarySensorEntityDescription(
        key="system_debug",
        translation_key="nextcloud_system_debug",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "system_enable_avatars": BinarySensorEntityDescription(
        key="system_enable_avatars",
        translation_key="nextcloud_system_enable_avatars",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "system_enable_previews": BinarySensorEntityDescription(
        key="system_enable_previews",
        translation_key="nextcloud_system_enable_previews",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "system_filelocking.enabled": BinarySensorEntityDescription(
        key="system_filelocking.enabled",
        translation_key="nextcloud_system_filelocking_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud binary sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudBinarySensor(coordinator, name, entry, BINARY_SENSORS[name])
            for name in coordinator.data
            if name in BINARY_SENSORS
        ]
    )


class NextcloudBinarySensor(NextcloudEntity, BinarySensorEntity):
    """Represents a Nextcloud binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        val = self.coordinator.data.get(self.item)
        return val is True or val == "yes"
