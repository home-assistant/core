"""
Demo platform for the geo location component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging
import random
from datetime import timedelta
from math import pi, cos, sin, radians

from typing import Optional

from homeassistant.components import group
from homeassistant.components.geo_location import GeoLocationEvent, DOMAIN
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_time_interval
from homeassistant import util

_LOGGER = logging.getLogger(__name__)

AVG_KM_PER_DEGREE = 111.0
DEFAULT_UNIT_OF_MEASUREMENT = "km"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)
ENTITY_ID_FORMAT = DOMAIN + '.{}'
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


class DemoManager:
    """Device manager for demo geo location events."""

    def __init__(self, hass, add_devices):
        """Initialise the demo geo location event manager."""
        self._hass = hass
        self._add_devices = add_devices
        self._name = "Geo Location Demo"
        self._managed_devices = []
        self.group = group.Group.create_group(self._hass, self._name,
                                              object_id=util.slugify(
                                                  self._name))
        self._update(count=NUMBER_OF_DEMO_DEVICES)
        self._init_regular_updates()

    def _generate_entity_id(self, event_name):
        """Generate device entity id from the manager name and event name."""
        entity_ids = [device.entity_id for device in self._managed_devices]
        entity_id = generate_entity_id(ENTITY_ID_FORMAT,
                                       '{} {}'.format(self._name, event_name),
                                       entity_ids, hass=self._hass)
        return entity_id

    def _group_devices(self):
        """Re-group all entities."""
        # Sort entries in group by their state attribute (ascending).
        devices = sorted(self._managed_devices.copy(),
                         key=lambda device: device.state,
                         reverse=False)
        entity_ids = [device.entity_id for device in devices]
        # Update group.
        self.group.update_tracked_entity_ids(entity_ids)

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
        return DemoGeoLocationEvent(self._hass, entity_id, event_name,
                                    radius_in_km, latitude, longitude,
                                    DEFAULT_UNIT_OF_MEASUREMENT)

    def _init_regular_updates(self):
        """Schedule regular updates based on configured time interval."""
        track_time_interval(self._hass, lambda now: self._update(),
                            DEFAULT_UPDATE_INTERVAL)

    def _update(self, count=1):
        """Remove events and add new random events."""
        # Remove devices.
        for _ in range(1, count + 1):
            if self._managed_devices:
                device = random.choice(self._managed_devices)
                if device:
                    _LOGGER.debug("Removing %s", device)
                    self._managed_devices.remove(device)
                    self._hass.add_job(device.async_remove())
        # Generate new devices from events.
        new_devices = []
        for _ in range(1, count + 1):
            new_device = self._generate_random_event()
            _LOGGER.debug("Adding %s", new_device)
            new_devices.append(new_device)
            self._managed_devices.append(new_device)
        self._add_devices(new_devices)
        self._group_devices()


class DemoGeoLocationEvent(GeoLocationEvent):
    """This represents a demo geo location event."""

    def __init__(self, hass, entity_id, name, distance, latitude, longitude,
                 unit_of_measurement):
        """Initialize entity with data provided."""
        super().__init__()
        self.hass = hass
        self.entity_id = entity_id
        self._name = name
        self._distance = distance
        self._latitude = latitude
        self._longitude = longitude
        self._unit_of_measurement = unit_of_measurement

    @property
    def name(self) -> Optional[str]:
        """Return the name of the event."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo geo location event."""
        return False

    @property
    def distance(self) -> Optional[float]:
        """Return distance value of this external event."""
        return self._distance

    @property
    def latitude(self):
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self):
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement
