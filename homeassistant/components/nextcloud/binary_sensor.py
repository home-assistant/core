"""Summary binary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

BINARY_SENSORS = (
    "nextcloud_system_enable_avatars",
    "nextcloud_system_enable_previews",
    "nextcloud_system_filelocking.enabled",
    "nextcloud_system_debug",
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Nextcloud sensors."""
    if discovery_info is None:
        return
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN]

    add_entities(
        [
            NextcloudBinarySensor(coordinator, name)
            for name in coordinator.data
            if name in BINARY_SENSORS
        ],
        True,
    )


class NextcloudBinarySensor(NextcloudEntity, BinarySensorEntity):
    """Represents a Nextcloud binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.get(self.item) == "yes"
