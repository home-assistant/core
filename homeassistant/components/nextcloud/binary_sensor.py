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
    "jit enabled": BinarySensorEntityDescription(
        key="jit enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "jit on": BinarySensorEntityDescription(
        key="jit on",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "system debug": BinarySensorEntityDescription(
        key="system debug", entity_category=EntityCategory.DIAGNOSTIC
    ),
    "system enable_avatars": BinarySensorEntityDescription(
        key="system enable_avatars", entity_category=EntityCategory.DIAGNOSTIC
    ),
    "system enable_previews": BinarySensorEntityDescription(
        key="system enable_previews", entity_category=EntityCategory.DIAGNOSTIC
    ),
    "system filelocking.enabled": BinarySensorEntityDescription(
        key="system filelocking.enabled", entity_category=EntityCategory.DIAGNOSTIC
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
