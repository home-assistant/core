from datetime import timedelta
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from . import DroneMobileEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Entities from the config."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    if "latitude" in entry.data["last_known_state"]:
        async_add_entities([CarTracker(entry, "gps")], True)
    else:
        _LOGGER.debug("Vehicle does not support GPS")


class CarTracker(DroneMobileEntity, TrackerEntity):
    def __init__(self, coordinator, sensor):

        self._attr = {}
        self.sensor = sensor
        self.coordinator = coordinator
        self._device_id = "dronemobile_tracker"

    @property
    def latitude(self):
        return float(self.coordinator.data["last_known_state"]["latitude"])

    @property
    def longitude(self):
        return float(self.coordinator.data["last_known_state"]["longitude"])

    @property
    def source_type(self):
        return SOURCE_TYPE_GPS

    @property
    def name(self):
        return "dronemobile_tracker"

    @property
    def device_id(self):
        return self.device_id

    @property
    def device_state_attributes(self):
        return self.coordinator.data.items()

    @property
    def icon(self):
        return "mdi:radar"
