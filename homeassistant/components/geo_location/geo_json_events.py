"""
Generic GeoJSON events platform.

Retrieves current events (typically incidents or alerts) in GeoJSON format, and
displays information on events filtered by distance to the HA instance's
location.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/geo_location/geo_json_events/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from typing import Optional

from geojson import Polygon

import homeassistant.helpers.config_validation as cv
from homeassistant.components.geo_location import GeoLocationEvent
from homeassistant.components.sensor.rest import RestData
from homeassistant.const import CONF_RADIUS, CONF_URL, CONF_SCAN_INTERVAL, \
    EVENT_HOMEASSISTANT_START, ATTR_ID, LENGTH_KILOMETERS, LENGTH_METERS
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import distance as util_distance
from homeassistant.util import location as util_location

REQUIREMENTS = ['geojson==2.4.0']

_LOGGER = logging.getLogger(__name__)

ATTR_CATEGORY = 'category'
ATTR_DISTANCE = 'distance'
ATTR_FEATURE = 'feature'
ATTR_GEOMETRY = 'geometry'
ATTR_GUID = 'guid'
ATTR_TITLE = 'title'

CONF_CATEGORIES = 'categories'

DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
DEFAULT_UNIT_OF_MEASUREMENT = "km"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM):
        vol.Coerce(float),
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        cv.time_period,
    vol.Optional(CONF_CATEGORIES, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, disc_info=None):
    """Set up the GeoJSON Events platform."""
    url = config.get(CONF_URL)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    radius_in_km = config.get(CONF_RADIUS)
    categories = config.get(CONF_CATEGORIES)
    # Initialize the device manager.
    GeoJsonFeedManager(hass, add_entities, url, scan_interval, radius_in_km,
                       categories)


class GeoJsonFeedManager:
    """Feed Manager for GeoJSON feeds."""

    def __init__(self, hass, add_entities, url, scan_interval, radius_in_km,
                 categories):
        """Initialize the GeoJSON Feed Manager."""
        self._hass = hass
        self._rest = RestData('GET', url, None, '', '', True)
        self._scan_interval = scan_interval
        self._add_entities = add_entities
        self._geo_distance_helper = GeoJsonDistanceHelper(hass)
        self._radius_in_km = radius_in_km
        self._categories = categories
        self._managed_devices = []
        hass.bus.listen_once(
            EVENT_HOMEASSISTANT_START, lambda _: self._update())
        self._init_regular_updates()

    def _init_regular_updates(self):
        """Schedule regular updates at the specified interval."""
        track_time_interval(self._hass, lambda now: self._update(),
                            self._scan_interval)

    def _update(self):
        """Update the feed and then update connected devices."""
        import geojson
        self._rest.update()
        value = self._rest.data
        if value is None:
            _LOGGER.warning("No data retrieved from %s", self._rest)
            # Remove all devices.
            self._update_or_remove_devices([])
        else:
            _LOGGER.warning("Data retrieved %s", value)
            filtered_entries = self._filter_entries(geojson.loads(value))
            keep_entries = self._update_or_remove_devices(filtered_entries)
            self._generate_new_devices(keep_entries)

    def _filter_entries(self, feature_collection):
        """Filter entries by distance from home coordinates."""
        keep_entries = []
        for feature in feature_collection.features:
            # Filter by category.
            if self._matches_category(feature):
                # Filter by distance.
                distance = self._geo_distance_helper.distance_to_geometry(
                    feature.geometry)
                _LOGGER.debug("Entry %s has distance %s", feature, distance)
                if distance and distance <= self._radius_in_km:
                    # Add distance value as a new attribute
                    entry = {ATTR_FEATURE: feature,
                             ATTR_DISTANCE: distance}
                    keep_entries.append(entry)
        _LOGGER.debug("%s entries found nearby after filtering",
                      len(keep_entries))
        return keep_entries

    def _matches_category(self, feature):
        """Check if the provided feature matches any of the categories."""
        if self._categories:
            if 'category' in feature.properties:
                return feature.properties.category in self._categories
            # Entry has no category.
            return False
        # No categories defined - always match.
        return True

    def _update_or_remove_devices(self, entries):
        """Update existing devices and remove obsolete devices."""
        _LOGGER.debug("Entries for updating: %s", entries)
        remove_entry = None
        # Remove obsolete entities for events that have disappeared
        managed_devices = self._managed_devices.copy()
        for device in managed_devices:
            # Remove entry from previous iteration - if applicable.
            if remove_entry:
                entries.remove(remove_entry)
                remove_entry = None
            for entry in entries:
                feature = entry[ATTR_FEATURE]
                entry_id = self._external_id(feature)
                if device.external_id == entry_id:
                    # Existing device - update details.
                    _LOGGER.debug("Existing device found %s", device)
                    remove_entry = entry
                    # Update existing device's details with event data.
                    latitude, longitude, _, name, category = \
                        self._extract_data(feature)
                    device.distance = entry[ATTR_DISTANCE]
                    device.latitude = latitude
                    device.longitude = longitude
                    device.name = name
                    device.category = category
                    break
            else:
                # Remove obsolete device.
                _LOGGER.debug("Device not current anymore %s", device)
                self._managed_devices.remove(device)
                self._hass.add_job(device.async_remove())
        # Remove entry from very last iteration - if applicable.
        if remove_entry:
            entries.remove(remove_entry)
        # Return the remaining entries that new devices must be created for.
        return entries

    def _generate_new_devices(self, entries):
        """Generate new entities for events."""
        new_devices = []
        for entry in entries:
            feature = entry[ATTR_FEATURE]
            latitude, longitude, external_id, name, category = \
                self._extract_data(feature)
            new_device = GeoJsonLocationEvent(entry[ATTR_DISTANCE], latitude,
                                              longitude, external_id, name,
                                              category)
            _LOGGER.debug("New device added %s", new_device)
            new_devices.append(new_device)
        # Add new devices to HA and keep track of them in this manager.
        self._add_entities(new_devices)
        self._managed_devices.extend(new_devices)

    def _extract_data(self, feature):
        """Extract relevant data from the external event."""
        latitude, longitude = self._geo_distance_helper.extract_coordinates(
            feature.geometry)
        title = None if ATTR_TITLE not in feature.properties else \
            feature.properties[ATTR_TITLE]
        category = None if ATTR_CATEGORY not in feature.properties else \
            feature.properties[ATTR_CATEGORY]
        return latitude, longitude, self._external_id(feature), title, category

    @staticmethod
    def _external_id(feature):
        """Find a suitable ID for the provided entry."""
        if hasattr(feature, ATTR_ID):
            return feature.id
        if ATTR_GUID in feature.properties:
            return feature.properties[ATTR_GUID]
        if ATTR_TITLE in feature.properties:
            return feature.properties[ATTR_TITLE]
        # Use geometry as ID as a fallback.
        return id(feature.geometry)


class GeoJsonDistanceHelper:
    """Helper to calculate distances between GeoJSON geometries."""

    def __init__(self, hass):
        """Initialize the geo distance helper."""
        self._hass = hass

    def extract_coordinates(self, geometry):
        """Extract the best geometry from the provided feature for display."""
        from geojson import Point, GeometryCollection
        latitude = longitude = None
        if type(geometry) is Point:
            # Just extract latitude and longitude directly.
            latitude, longitude = geometry.coordinates[1], \
                                  geometry.coordinates[0]
        elif type(geometry) is GeometryCollection:
            # Go through the collection, and extract the first suitable
            # geometry.
            for geometry in geometry.geometries:
                latitude, longitude = self.extract_coordinates(geometry)
                if latitude is not None and longitude is not None:
                    break
        elif type(geometry) is Polygon:
            # Find the polygon's centroid as a best approximation for the map.
            longitudes_list = [point[0] for point in geometry.coordinates[0]]
            latitudes_list = [point[1] for point in geometry.coordinates[0]]
            number_of_points = len(geometry.coordinates[0])
            longitude = sum(longitudes_list) / number_of_points
            latitude = sum(latitudes_list) / number_of_points
            _LOGGER.debug("Centroid of %s is %s", geometry.coordinates[0],
                          (latitude, longitude))
        else:
            _LOGGER.debug("Not implemented: %s", type(geometry))
        return latitude, longitude

    def distance_to_geometry(self, geometry):
        """Calculate the distance between home coordinates and geometry."""
        from geojson import Point, GeometryCollection
        distance = float("inf")
        if type(geometry) is Point:
            distance = self._distance_to_point(geometry)
        elif type(geometry) is GeometryCollection:
            distance = self._distance_to_geometry_collection(geometry)
        elif type(geometry) is Polygon:
            distance = self._distance_to_polygon(geometry.coordinates[0])
        else:
            _LOGGER.debug("Not implemented: %s", type(geometry))
        return distance

    def _distance_to_point(self, point):
        """Calculate the distance between HA and the provided point."""
        # Swap coordinates to match: (latitude, longitude).
        return self._distance_to_coordinates(point.coordinates[1],
                                             point.coordinates[0])

    def _distance_to_geometry_collection(self, geometry_collection):
        """Calculate the distance between HA and the provided geometries."""
        distance = float("inf")
        for geometry in geometry_collection.geometries:
            distance = min(distance, self.distance_to_geometry(geometry))
        return distance

    def _distance_to_polygon(self, polygon):
        """Calculate the distance between HA and the provided polygon."""
        distance = float("inf")
        # Calculate distance from polygon by calculating the distance
        # to each point of the polygon but not to each edge of the
        # polygon; should be good enough
        for polygon_point in polygon:
            distance = min(distance,
                           self._distance_to_coordinates(polygon_point[1],
                                                         polygon_point[0]))
        return distance

    def _distance_to_coordinates(self, latitude, longitude):
        """Calculate the distance between HA and the provided coordinates."""
        # Expecting coordinates in format: (latitude, longitude).
        return util_distance.convert(util_location.distance(
            self._hass.config.latitude, self._hass.config.longitude, latitude,
            longitude), LENGTH_METERS, LENGTH_KILOMETERS)


class GeoJsonLocationEvent(GeoLocationEvent):
    """This represents an external event with GeoJSON data."""

    def __init__(self, distance, latitude, longitude, external_id, name,
                 category):
        """Initialize entity with data provided."""
        self._distance = distance
        self._latitude = latitude
        self._longitude = longitude
        self._external_id = external_id
        self._name = name
        self._category = category

    @property
    def should_poll(self):
        """No polling needed for GeoJSON location events."""
        return False

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._name

    @name.setter
    def name(self, value):
        """Set event's name."""
        self._name = value

    @property
    def distance(self) -> Optional[float]:
        """Return distance value of this external event."""
        return self._distance

    @distance.setter
    def distance(self, value):
        """Set event's distance."""
        self._distance = value

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of this external event."""
        return self._latitude

    @latitude.setter
    def latitude(self, value):
        """Set event's latitude."""
        self._latitude = value

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of this external event."""
        return self._longitude

    @longitude.setter
    def longitude(self, value):
        """Set event's longitude."""
        self._longitude = value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return DEFAULT_UNIT_OF_MEASUREMENT

    @property
    def external_id(self):
        """Return external id of this event."""
        return self._external_id

    @property
    def category(self):
        """Return the category of the event."""
        return self._category

    @category.setter
    def category(self, value):
        """Set event's category."""
        self._category = value

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {'name': self.name}
        if self.category:
            attributes['category'] = self.category
        if self.external_id:
            attributes['external id'] = self.external_id
        return attributes
