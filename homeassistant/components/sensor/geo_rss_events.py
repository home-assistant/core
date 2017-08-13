"""
Generic GeoRSS events service.

Retrieves current events (typically incidents or alerts) in GeoRSS format, and
shows information on events filtered by distance to the HA instance's location
and grouped by category.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.geo_rss_events/
"""

import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (STATE_UNKNOWN, CONF_SCAN_INTERVAL,
                                 CONF_UNIT_OF_MEASUREMENT, CONF_NAME,
                                 CONF_ICON)
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['feedparser==5.2.1', 'haversine==0.4.5']

_LOGGER = logging.getLogger(__name__)

CONF_CATEGORIES = 'categories'
CONF_RADIUS = 'radius'
CONF_URL = 'url'

DEFAULT_ICON = 'mdi:alert'
DEFAULT_NAME = "Event Service"
DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
DEFAULT_UNIT_OF_MEASUREMENT = 'Events'

DOMAIN = 'geo_rss_events'
ENTITY_ID_FORMAT = 'sensor.' + DOMAIN + '_{}'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.icon,
    vol.Optional(CONF_CATEGORIES, default=[]): vol.All(cv.ensure_list,
                                                       [cv.string]),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT,
                 default=DEFAULT_UNIT_OF_MEASUREMENT): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):  # pragma: no cover
    """Set up the GeoRSS component."""
    # Grab location from config
    home_latitude = hass.config.latitude
    home_longitude = hass.config.longitude
    url = config.get(CONF_URL)
    radius_in_km = config.get(CONF_RADIUS)
    name = config.get(CONF_NAME)
    icon = config.get(CONF_ICON)
    categories = config.get(CONF_CATEGORIES)
    scan_interval = config.get(CONF_SCAN_INTERVAL) or DEFAULT_SCAN_INTERVAL
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    if None in (home_latitude, home_longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    _LOGGER.debug("latitude=%s, longitude=%s, url=%s, radius=%s",
                  home_latitude, home_longitude, url, radius_in_km)

    data = GeoRssServiceData()

    # Create all sensors based on categories.
    devices = []
    if not categories:
        device = GeoRssServiceSensor(hass, None, [], name, icon,
                                     unit_of_measurement)
        devices.append(device)
    else:
        for category in categories:
            device = GeoRssServiceSensor(hass, category, data, name, icon,
                                         unit_of_measurement)
            devices.append(device)
    async_add_devices(devices)

    # Initialise update service.
    updater = GeoRssServiceUpdater(hass, data, home_latitude, home_longitude,
                                   url, radius_in_km, devices)
    async_track_time_interval(hass, updater.async_update, scan_interval)
    yield from updater.async_update()
    return True


class GeoRssServiceSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, category, data, name, icon,
                 unit_of_measurement):
        """Initialize the sensor."""
        self.hass = hass
        self._category = category
        self._data = data
        self._state = STATE_UNKNOWN
        self._name = name
        self._icon = icon
        self._unit_of_measurement = unit_of_measurement
        if category is not None:
            id_base = category
        else:
            id_base = 'any'
        if name is not None:
            id_base = '{}_{}'.format(name, id_base)
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, id_base,
                                                  hass=hass)

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._category is not None:
            return self._category
        else:
            return 'Any'

    @property
    def state(self):
        """Return the state of the sensor."""
        if isinstance(self._state, list):
            return len(self._state)
        else:
            return self._state

    @property
    def should_poll(self):  # pylint: disable=no-self-use
        """No polling needed."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        matrix = {}
        if self._state is not STATE_UNKNOWN:
            for event in self._state:
                matrix[event.title] = '{:.0f}km'.format(event.distance)
        return matrix

    def update(self):
        """Update this sensor from the GeoRSS service."""
        all_events = self._data.events
        if self._category is None:
            # Add all events regardless of category.
            self._state = all_events
        else:
            # Group events by category.
            my_events = []
            for event in all_events:
                if event.category == self._category:
                    my_events.append(event)
            self._state = my_events
            _LOGGER.info("New state: %s", self._state)


class GeoRssServiceData(object):
    """Stores the latest data from the GeoRSS service."""

    def __init__(self):
        """Initialize the data object."""
        self.events = None


class GeoRssServiceUpdater:
    """Provides access to GeoRSS feed and creates and updates UI devices."""

    def __init__(self, hass, data, home_latitude, home_longitude, url,
                 radius_in_km, devices):
        """Initialize the update service."""
        self._hass = hass
        self._data = data
        self._home_coordinates = [home_latitude, home_longitude]
        self._url = url
        self._radius_in_km = radius_in_km
        self._devices = devices

    @asyncio.coroutine
    def async_update(self, *_):  # pragma: no cover
        """Retrieve data from GeoRSS feed and update devices."""
        import feedparser
        feed_data = feedparser.parse(self._url)
        if not feed_data:
            _LOGGER.error("Error fetching feed data from %s", self._url)
        else:
            events = self.filter_entries(feed_data)
            self._data.events = events
            # Update devices.
            tasks = []
            if self._devices:
                for device in self._devices:
                    tasks.append(device.async_update_ha_state(True))
            if tasks:
                yield from asyncio.wait(tasks, loop=self._hass.loop)

    def filter_entries(self, feed_data):
        """Filter entries by distance from home coordinates."""
        events = []
        _LOGGER.info("%s entri(es) available in feed %s",
                     len(feed_data.entries), self._url)
        for entry in feed_data.entries:
            geometry = None
            if hasattr(entry, 'where'):
                geometry = entry.where
            elif hasattr(entry, 'geo_lat') and hasattr(entry, 'geo_long'):
                coordinates = (float(entry.geo_long), float(entry.geo_lat))
                geometry = type('obj', (object,),
                                {'type': 'Point', 'coordinates': coordinates})
            if geometry:
                distance = self.calculate_distance_to_geometry(geometry)
            if distance <= self._radius_in_km:
                event = self.create_event(entry, distance, geometry)
                events.append(event)
        _LOGGER.info("Events found nearby: %s", events)
        return events

    @staticmethod
    def create_event(feature, distance, geometry):
        """Create an event from the RSS feed's entry and geo information."""
        category_candidate = None
        if hasattr(feature, 'category'):
            category_candidate = feature.category
        title_candidate = None
        if hasattr(feature, 'title'):
            title_candidate = feature.title
        id_candidate = None
        if hasattr(feature, 'id'):
            id_candidate = feature.id
        elif hasattr(feature, 'link'):
            id_candidate = feature.link
        pup_date_candidate = None
        if hasattr(feature, 'updated_parsed'):
            pup_date_candidate = feature.updated_parsed
        elif hasattr(feature, 'published_parsed'):
            pup_date_candidate = feature.published_parsed
        summary_candidate = None
        if hasattr(feature, 'summary'):
            summary_candidate = feature.summary
        return Event(category_candidate,
                     title_candidate,
                     id_candidate,
                     pup_date_candidate,
                     summary_candidate,
                     geometry,
                     distance)

    def calculate_distance_to_geometry(self, geometry):
        """Calculate the distance between HA and provided geometry."""
        distance = float("inf")
        if geometry.type == 'Point':
            distance = self.calculate_distance_to_point(geometry)
        elif geometry.type == 'Polygon':
            distance = self.calculate_distance_to_polygon(
                geometry.coordinates[0])
        else:
            _LOGGER.info("Not yet implemented: %s", geometry.type)
        return distance

    def calculate_distance_to_point(self, point):
        """Calculate the distance between HA and the provided point."""
        # Swap coordinates to match: (lat, lon).
        coordinates = (point.coordinates[1], point.coordinates[0])
        return self.calculate_distance_to_coords(coordinates)

    def calculate_distance_to_coords(self, coordinates):
        """Calculate the distance between HA and the provided coordinates."""
        # Expecting coordinates in format: (lat, lon).
        from haversine import haversine
        distance = haversine(coordinates, self._home_coordinates)
        _LOGGER.debug("Distance from %s to %s: %s km", self._home_coordinates,
                      coordinates, distance)
        return distance

    def calculate_distance_to_polygon(self, polygon):
        """Calculate the distance between HA and the provided polygon."""
        distance = float("inf")
        # Calculate distance from polygon by calculating the distance
        # to each point of the polygon but not to each edge of the
        # polygon; should be good enough
        number_of_points = len(polygon)
        for i in range(number_of_points):
            polygon_point = polygon[i]
            coordinates = (polygon_point[1], polygon_point[0])
            distance = min(distance,
                           self.calculate_distance_to_coords(coordinates))
        _LOGGER.debug("Distance from %s to %s: %s km", self._home_coordinates,
                      polygon, distance)
        return distance


class Event(object):
    """Class for storing events retrieved."""

    def __init__(self, category, title, guid, pub_date, description, geometry,
                 distance):
        """Initialize the data object."""
        self._category = category
        self._title = title
        self._guid = guid
        self._pub_date = pub_date
        self._description = description
        self._geometry = geometry
        self._distance = distance

    @property
    def category(self):
        """Return the event's category."""
        return self._category

    @property
    def title(self):
        """Return the event's title."""
        return self._title

    @property
    def guid(self):
        """Return the event's GUID."""
        return self._guid

    @property
    def pub_date(self):
        """Return the event's publication date."""
        return self._pub_date

    @property
    def description(self):
        """Return the event's description."""
        return self._description

    @property
    def geometry(self):
        """Return the event's geometry details."""
        return self._geometry

    @property
    def distance(self):
        """Return the event's distance to HA in km."""
        return self._distance
