"""Platform for Mazda device tracker integration."""
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the device tracker platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities = []

    for index, _ in enumerate(coordinator.data):
        entities.append(MazdaDeviceTracker(client, coordinator, index))

    async_add_entities(entities)


class MazdaDeviceTracker(MazdaEntity, TrackerEntity):
    """Class for the device tracker."""

    _attr_translation_key = "device_tracker"
    _attr_icon = "mdi:car"
    _attr_force_update = False

    def __init__(self, client, coordinator, index) -> None:
        """Initialize Mazda device tracker."""
        super().__init__(client, coordinator, index)

        self._attr_unique_id = self.vin

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self.data["status"]["latitude"]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self.data["status"]["longitude"]
