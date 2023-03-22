"""Demo platform for the geolocation component."""
from __future__ import annotations

from datetime import timedelta
import logging
from math import cos, pi, radians, sin
import random

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

AVG_KM_PER_DEGREE = 111.0
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)
MAX_RADIUS_IN_KM = 50
NUMBER_OF_DEMO_DEVICES = 5

EVENT_NAMES = [
    "Bushfire",
    "Hazard Reduction",
    "Grass Fire",
    "Burn off",
    "Structure Fire",
    "Fire Alarm",
    "Thunderstorm",
    "Tornado",
    "Cyclone",
    "Waterspout",
    "Dust Storm",
    "Blizzard",
    "Ice Storm",
    "Earthquake",
    "Tsunami",
]

SOURCE = "demo"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo geolocations."""
    DemoManager(hass, add_entities)


class DemoManager:
    """Device manager for demo geolocation events."""

    def __init__(self, hass: HomeAssistant, add_entities: AddEntitiesCallback) -> None:
        """Initialise the demo geolocation event manager."""
        self._hass = hass
        self._add_entities = add_entities
        self._managed_devices: list[DemoGeolocationEvent] = []
        self._update(count=NUMBER_OF_DEMO_DEVICES)
        self._init_regular_updates()

    def _generate_random_event(self) -> DemoGeolocationEvent:
        """Generate a random event in vicinity of this HA instance."""
        home_latitude = self._hass.config.latitude
        home_longitude = self._hass.config.longitude

        # Approx. 111km per degree (north-south).
        radius_in_degrees = random.random() * MAX_RADIUS_IN_KM / AVG_KM_PER_DEGREE
        radius_in_km = radius_in_degrees * AVG_KM_PER_DEGREE
        angle = random.random() * 2 * pi
        # Compute coordinates based on radius and angle. Adjust longitude value
        # based on HA's latitude.
        latitude = home_latitude + radius_in_degrees * sin(angle)
        longitude = home_longitude + radius_in_degrees * cos(angle) / cos(
            radians(home_latitude)
        )

        event_name = random.choice(EVENT_NAMES)
        return DemoGeolocationEvent(
            event_name, radius_in_km, latitude, longitude, UnitOfLength.KILOMETERS
        )

    def _init_regular_updates(self) -> None:
        """Schedule regular updates based on configured time interval."""
        track_time_interval(
            self._hass, lambda now: self._update(), DEFAULT_UPDATE_INTERVAL
        )

    def _update(self, count: int = 1) -> None:
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
        self._add_entities(new_devices)


class DemoGeolocationEvent(GeolocationEvent):
    """Represents a demo geolocation event."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        distance: float,
        latitude: float,
        longitude: float,
        unit_of_measurement: str,
    ) -> None:
        """Initialize entity with data provided."""
        self._attr_name = name
        self._distance = distance
        self._latitude = latitude
        self._longitude = longitude
        self._unit_of_measurement = unit_of_measurement

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return SOURCE

    @property
    def distance(self) -> float | None:
        """Return distance value of this external event."""
        return self._distance

    @property
    def latitude(self) -> float | None:
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement
