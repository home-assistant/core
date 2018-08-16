"""
Demo platform for the geo location component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging
import random
from datetime import timedelta
from math import pi, cos, sin, radians

from homeassistant.components.geo_location import GeoLocationEvent, \
    GeoLocationDeviceManager, DEFAULT_SORT_GROUP_ENTRIES_REVERSE
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

AVG_KM_PER_DEGREE = 111.0
DEFAULT_UNIT_OF_MEASUREMENT = "km"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)
MAX_RADIUS_IN_KM = 50
NUMBER_OF_DEMO_DEVICES = 5

EVENT_NAMES = ["Bushfire", "Hazard Reduction", "Grass Fire", "Burn off",
               "Structure Fire", "Fire Alarm", "Thunderstorm", "Tornado",
               "Cyclone", "Waterspout", "Dust Storm", "Blizzard", "Ice Storm",
               "Earthquake", "Tsunami"]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo geo locations."""
    manager = DemoManager(hass, add_devices)
    return manager is not None


class DemoManager(GeoLocationDeviceManager):
    """Device manager for demo geo location events."""

    def __init__(self, hass, add_devices):
        """Initialise the demo geo location event manager."""
        super().__init__(hass, add_devices, "Geo Location Demo",
                         DEFAULT_SORT_GROUP_ENTRIES_REVERSE)
        self._update(count=NUMBER_OF_DEMO_DEVICES)
        self._init_regular_updates()

    def _generate_random_event(self):
        """Generate a random event in vicinity of this HA instance."""
        home_latitude = self._hass.config.latitude
        home_longitude = self._hass.config.longitude

        # Approx. 111km per degree (north-south).
        radius_in_degrees = random.random() * MAX_RADIUS_IN_KM / \
            AVG_KM_PER_DEGREE
        radius_in_km = radius_in_degrees * AVG_KM_PER_DEGREE
        angle = random.random() * 2 * pi
        # Compute coordinates based on radius and angle. Adjust longitude value
        # based on HA's latitude.
        latitude = home_latitude + radius_in_degrees * sin(angle)
        longitude = home_longitude + radius_in_degrees * cos(angle) / \
            cos(radians(home_latitude))

        event_name = random.choice(EVENT_NAMES)
        entity_id = self._generate_entity_id(event_name)
        return GeoLocationEvent(self._hass, entity_id, event_name,
                                radius_in_km, latitude, longitude,
                                DEFAULT_UNIT_OF_MEASUREMENT, None)

    def _init_regular_updates(self):
        """Schedule regular updates based on configured time interval."""
        track_time_interval(self._hass, lambda now: self._update(),
                            DEFAULT_UPDATE_INTERVAL)

    def _update(self, count=1):
        """Remove events and add new random events."""
        # Remove devices.
        for i in range(1, count + 1):
            if self._managed_devices:
                device = random.choice(self._managed_devices)
                if device:
                    _LOGGER.debug("Removing %s", device)
                    self._managed_devices.remove(device)
                    self._hass.add_job(device.async_remove())
        # Generate new devices from events.
        new_devices = []
        for i in range(1, count + 1):
            new_device = self._generate_random_event()
            _LOGGER.debug("Adding %s", new_device)
            new_devices.append(new_device)
            self._managed_devices.append(new_device)
        self._add_devices(new_devices)
        self._group_devices()
