"""Summary binary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, isbool, istrue
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

BINARY_SENSORS: dict[str, dict] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud binary sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudBinarySensor(
                coordinator, name, entry, attrs=BINARY_SENSORS.get(name)
            )
            for name in coordinator.data
            if isbool(coordinator.data[name])
        ]
    )


class NextcloudBinarySensor(NextcloudEntity, BinarySensorEntity):
    """Represents a Nextcloud binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return istrue(self.coordinator.data.get(self.item))
