"""Platform for Mazda device tracker integration."""
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from . import MazdaEntity
from .const import DATA_COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the device tracker platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities = []

    for index, _ in enumerate(coordinator.data):
        entities.append(MazdaDeviceTracker(coordinator, index))

    async_add_entities(entities)


class MazdaDeviceTracker(MazdaEntity, TrackerEntity):
    """Class for the device tracker."""

    @property
    def name(self):
        """Return the name of the entity."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Device Tracker"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return self.vin

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car"

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def force_update(self):
        """All updates do not need to be written to the state machine."""
        return False

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self.coordinator.data[self.index]["status"]["latitude"]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self.coordinator.data[self.index]["status"]["longitude"]
