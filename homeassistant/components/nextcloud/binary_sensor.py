"""Summary binary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

BINARY_SENSORS = (
    "nextcloud_system_enable_avatars",
    "nextcloud_system_enable_previews",
    "nextcloud_system_filelocking.enabled",
    "nextcloud_system_debug",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud binary sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudBinarySensor(coordinator, name, entry)
            for name in coordinator.data
            if name in BINARY_SENSORS
        ]
    )


class NextcloudBinarySensor(NextcloudEntity, BinarySensorEntity):
    """Represents a Nextcloud binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.get(self.item) == "yes"
