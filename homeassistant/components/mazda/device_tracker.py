"""Platform for Mazda device tracker integration."""
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the device tracker platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities = []

    for index, _ in enumerate(coordinator.data):
        entities.append(MazdaDeviceTracker(client, coordinator, index))

    async_add_entities(entities)


class MazdaDeviceTracker(MazdaEntity, TrackerEntity):
    """Class for the device tracker."""

    def __init__(self, client, coordinator, index) -> None:
        """Initialize Mazda device tracker."""
        super().__init__(client, coordinator, index)

        self._attr_name = f"{self.vehicle_name} Device Tracker"
        self._attr_unique_id = self.vin
        self._attr_icon = "mdi:car"
        self._attr_force_update = False

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self.data["status"]["latitude"]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self.data["status"]["longitude"]
