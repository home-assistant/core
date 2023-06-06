"""Summary binary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BOOLEAN_TRUE_VALUES, BOOLEN_VALUES, DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud binary sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudBinarySensor(coordinator, name, entry, None)
            for name in coordinator.data
            if isinstance(coordinator.data[name], bool)
            or coordinator.data[name] in BOOLEN_VALUES
        ]
    )


class NextcloudBinarySensor(NextcloudEntity, BinarySensorEntity):
    """Represents a Nextcloud binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        val = self.coordinator.data.get(self.item)
        return val is True or val in BOOLEAN_TRUE_VALUES
