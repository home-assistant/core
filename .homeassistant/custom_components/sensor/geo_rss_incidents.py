"""
Generic GeoRSS service
Retrieves current incidents or alerts in GeoRSS format, and shows information on incidents filtered by distance
to the HA instance's location and grouped by category.

Example configuration:

sensor:
  - platform: geo_rss_incidents
    name: NSW Fire Service
    url: http://www.rfs.nsw.gov.au/feeds/majorIncidents.xml
    icon: mdi:fire
    radius: 25
    categories:
      - 'Emergency Warning'
      - 'Watch and Act'
      - 'Advice'
      - 'Not Applicable'
    unit_of_measurement: 'Incidents'

Sample feeds

Fire
- NSW Rural Fire Service: http://www.rfs.nsw.gov.au/feeds/majorIncidents.xml
- Qld Rural Fire Service: https://www.qfes.qld.gov.au/data/alerts/bushfireAlert.xml
- ACT Emergency Services Agency: http://www.esa.act.gov.au/feeds/currentincidents.xml
- WA Department of Fire and Emergency Services: https://www.emergency.wa.gov.au/data/incident_FCAD.rss
- Tasmania Fire Service: http://www.fire.tas.gov.au/Show?pageId=colBushfireSummariesRss

Earthquake
- USGS: https://earthquake.usgs.gov/earthquakes/feed/v1.0/atom.php
- BGS: http://www.bgs.ac.uk/feeds/worldSeismology.xml


"""
import asyncio
import logging
import json
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (STATE_UNKNOWN, CONF_SCAN_INTERVAL, CONF_UNIT_OF_MEASUREMENT, CONF_NAME, CONF_ICON)
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['feedparser==5.2.1', 'haversine==0.4.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'geo_rss'
ENTITY_ID_FORMAT = 'sensor.' + DOMAIN + '_{}'
INCIDENTS = 'incidents'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

CONF_URL = 'url'
CONF_RADIUS = 'radius'
CONF_CATEGORIES = 'categories'

DEFAULT_NAME = 'Incident Information Service'
# DEFAULT_URL = 'http://www.rfs.nsw.gov.au/feeds/majorIncidents.xml'
DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_UNIT_OF_MEASUREMEMT = 'Incident'
DEFAULT_ICON = 'mdi:alert'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.icon,
    vol.Required(CONF_CATEGORIES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DEFAULT_UNIT_OF_MEASUREMEMT): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    # Grab location from config
    home_latitude = hass.config.latitude
    home_longitude = hass.config.longitude
    url = config.get(CONF_URL)
    radius_in_km = config.get(CONF_RADIUS)
    name = config.get(CONF_NAME)
    icon = config.get(CONF_ICON)
    categories = config.get(CONF_CATEGORIES)
    interval_in_seconds = config.get(CONF_SCAN_INTERVAL) or timedelta(minutes=5)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    if None in (home_latitude, home_longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    _LOGGER.debug("latitude=%s, longitude=%s, url=%s, radius=%s", home_latitude,
                  home_longitude, url, radius_in_km)

    # create all sensors
    devices = []
    devices_by_category = {}
    for category in categories:
        device = GeoRssServiceSensor(hass, category, [], name, icon, unit_of_measurement)
        devices.append(device)
        devices_by_category[category] = device
    async_add_devices(devices)

    # initialise access to web resource
    updater = GeoRssServiceUpdater(hass, home_latitude, home_longitude, url, radius_in_km,
                                   devices_by_category)
    async_track_time_interval(hass, updater.async_update, interval_in_seconds)
    yield from updater.async_update()
    return True


class GeoRssServiceSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, category, incidents, name, icon, unit_of_measurement):
        """Initialize the sensor."""
        self.hass = hass
        self._category = category
        self._state = incidents
        self._name = name
        self._icon = icon
        self._unit_of_measurement = unit_of_measurement
        id_base = category
        if name is not None:
            id_base = '{}_{})'.format(name, category)
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, id_base,
                                                  hass=hass)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._category

    @property
    def state(self):
        """Return the state of the sensor."""
        if isinstance(self._state, list):
            return len(self._state)
        else:
            return self._state

    @state.setter
    def state(self, value):
        self._state = value

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
        for incident in self._state:
            matrix[incident.title] = '{:.0f}km'.format(incident.distance)
        return matrix


class GeoRssServiceUpdater:
    """Provides access to GeoRSS and creates and updates UI devices."""

    def __init__(self, hass, home_latitude, home_longitude, url,
                 radius_in_km, devices_by_category):
        """Initialize the sensor."""
        self._hass = hass
        self._feed = None
        self._home_latitude = home_latitude
        self._home_longitude = home_longitude
        self._home_coordinates = [home_longitude, home_latitude]
        self._url = url
        self._radius_in_km = radius_in_km
        self._state = STATE_UNKNOWN
        self._devices_by_category = devices_by_category

    @asyncio.coroutine
    def async_update(self, *_):
        import feedparser
        # retrieve data
        self._feed = feedparser.parse(self._url)
        if not self._feed:
            _LOGGER.error("Error fetching feed data from %s", self._url)
        else:
            incidents = []
            _LOGGER.info("%s entri(es) available in feed %s",
                         len(self._feed.entries), self._url)
            # filter entries by distance from home
            for entry in self._feed.entries:
                #print(entry)
                if hasattr(entry, 'where'):
                    distance = self.calculate_distance_to_geometry(entry.where)
                elif hasattr(entry, 'geo_lat') and hasattr(entry, 'geo_long'):
                    coordinates = (float(entry.geo_lat), float(entry.geo_long))
                    distance = self.calculate_distance_to_coordinates(coordinates)
                if distance <= self._radius_in_km:
                    incident = self.create_incident(distance, entry)
                    incidents.append(incident)
            # group incidents by category
            incidents_by_category = {}
            for incident in incidents:
                if incident.category in incidents_by_category:
                    incidents_by_category[incident.category].append(incident)
                else:
                    incidents_by_category[incident.category] = [incident]
            _LOGGER.info("Incidents by category: %s", incidents_by_category)
            # set new state (incidents) on devices
            tasks = []
            for category in incidents_by_category.keys():
                # update existing device with new list of incidents
                if category in self._devices_by_category:
                    device = self._devices_by_category[category]
                    device.state = incidents_by_category[category]
                    tasks.append(device.async_update_ha_state())
            _LOGGER.info("Devices by category: %s", self._devices_by_category)
            if tasks:
                yield from asyncio.wait(tasks, loop=self._hass.loop)

    @staticmethod
    def create_incident(distance, feature):
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
        #print('Category:', feature.category)
        #print('Tags: ', feature.tags)
        return Incident(feature.category,
                        feature.title,
                        id_candidate,
                        pup_date_candidate,
                        feature.summary,
                        distance)

    def calculate_distance_to_geometry(self, geometry):
        distance = float("inf")
        if geometry.type == 'Point':
            distance = self.calculate_distance_to_point(geometry)
        elif geometry.type == 'Polygon':
            distance = self.calculate_distance_to_polygon(geometry.coordinates[0])
        else:
            _LOGGER.info("Not yet implemented: %s", geometry.type)
        return distance

    def calculate_distance_to_point(self, point):
        # from shapely.geometry import shape
        from haversine import haversine
        coordinates = point.coordinates
        return self.calculate_distance_to_coordinates(coordinates)

    def calculate_distance_to_coordinates(self, coordinates):
        # from shapely.geometry import shape
        from haversine import haversine
        distance = haversine(coordinates, self._home_coordinates)
        _LOGGER.debug("Distance from %s to %s: %s km", self._home_coordinates,
                      coordinates, distance)
        return distance

    def calculate_distance_to_polygon(self, polygon):
        from haversine import haversine
        distance = float("inf")
        # 1. Check if home coordinates are within polygon
        if self.point_in_polygon(self._home_coordinates, polygon):
            distance = 0
        else:
            # 2. Calculate distance from polygon by calculating the distance to each point of the polygon
            #    but not to each edge of the polygon; should be good enough
            n = len(polygon)
            for i in range(n):
                polygon_point = polygon[i]
                distance = min(distance, haversine(polygon_point, self._home_coordinates))
        _LOGGER.debug("Distance from %s to %s: %s km", self._home_coordinates,
                      polygon, distance)
        return distance

    @staticmethod
    def point_in_polygon(point, polygon):
        # Source: http://geospatialpython.com/2011/08/point-in-polygon-2-on-line.html
        x = point[0]
        y = point[1]
        # check if point is a vertex
        if point in polygon: return True

        # check if point is on a boundary
        for i in range(len(polygon)):
            p1 = None
            p2 = None
            if i == 0:
                p1 = polygon[0]
                p2 = polygon[1]
            else:
                p1 = polygon[i - 1]
                p2 = polygon[i]
            if p1[1] == p2[1] and p1[1] == y and x > min(p1[0], p2[0]) and x < max(p1[0], p2[0]):
                return True

        n = len(polygon)
        inside = False

        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside


class Incident(object):
    """Class for storing incidents retrieved."""

    def __init__(self, category, title, guid, pub_date, description, distance):
        """Initialize the data object."""
        self._category = category
        self._title = title
        self._guid = guid
        self._pub_date = pub_date
        self._description = description
        self._distance = distance

    @property
    def category(self):
        return self._category

    @property
    def title(self):
        return self._title

    @property
    def pub_date(self):
        return self._pub_date

    @property
    def description(self):
        return self._description

    @property
    def distance(self):
        return self._distance

    def __str__(self, *args, **kwargs):
        return json.dumps(self, default=lambda obj: vars(obj), indent=1)
