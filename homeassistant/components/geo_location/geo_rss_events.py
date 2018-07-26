"""
Generic GeoRSS events platform.

Retrieves current events (typically incidents or alerts) in GeoRSS format, and
displays information on events filtered by distance to the HA instance's
location.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/geo_location/geo_rss_events/
"""
import logging
from collections import namedtuple
from datetime import timedelta
import re

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.feedreader import StoredData, FeedManager
from homeassistant.components.geo_location import DOMAIN, GeoLocationEvent, \
    ENTITY_ID_FORMAT
from homeassistant.const import CONF_URL, CONF_RADIUS, CONF_NAME, \
    CONF_SCAN_INTERVAL, CONF_ICON
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_time_interval
from homeassistant import util

REQUIREMENTS = ['feedparser==5.2.1', 'haversine==0.4.5']

_LOGGER = logging.getLogger(__name__)

ATTR_CATEGORIES = "categories"
ATTR_CATEGORY = 'category'
ATTR_GEOMETRY = 'geometry'
ATTR_DISTANCE = 'distance'
ATTR_ID = 'id'
ATTR_MANAGER = "manager"
ATTR_TITLE = 'title'

CONF_CATEGORIES = 'categories'
CONF_ATTRIBUTES = 'attributes'
CONF_ATTRIBUTES_NAME = 'name'
CONF_ATTRIBUTES_REGEXP = 'regexp'
CONF_ATTRIBUTES_SOURCE = 'source'
CONF_CUSTOM_ATTRIBUTE = 'custom_attribute'
CONF_FILTERS = 'filters'
CONF_FILTERS_ATTRIBUTE = 'attribute'
CONF_FILTERS_REGEXP = 'regexp'
CONF_SENSOR_CATEGORY = 'category'
CONF_SENSOR_EVENT_TYPE = 'event_type'
CONF_SENSOR_NAME = 'name'

DEFAULT_ICON = 'mdi:alert'
DEFAULT_NAME = "Event Service"
DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

DEPENDENCIES = ['group']

ATTRIBUTES_SCHEMA = vol.Schema({
    vol.Required(CONF_ATTRIBUTES_NAME): cv.string,
    vol.Required(CONF_ATTRIBUTES_SOURCE): cv.string,
    vol.Required(CONF_ATTRIBUTES_REGEXP): cv.string,
})

FILTERS_SCHEMA = vol.Schema({
    vol.Required(CONF_FILTERS_ATTRIBUTE): cv.string,
    vol.Required(CONF_FILTERS_REGEXP): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM):
        vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        cv.time_period,
    vol.Optional(CONF_CATEGORIES, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_ATTRIBUTES, default=[]):
        vol.All(cv.ensure_list, [ATTRIBUTES_SCHEMA]),
    vol.Optional(CONF_FILTERS, default=[]):
        vol.All(cv.ensure_list, [FILTERS_SCHEMA]),
    vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.icon,
})


def setup_platform(hass, config, add_devices, disc_info=None):
    """Set up the GeoRSS platform."""
    home_latitude = hass.config.latitude
    home_longitude = hass.config.longitude
    data_file = hass.config.path("{}.pickle".format(DOMAIN))
    storage = StoredData(data_file)
    url = config.get(CONF_URL)
    radius_in_km = config.get(CONF_RADIUS)
    name = config.get(CONF_NAME)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    categories = config.get(CONF_CATEGORIES)
    # TODO: check that custom attribute don't override built-in ones
    attributes_definition = config.get(CONF_ATTRIBUTES)
    filters_definition = config.get(CONF_FILTERS)
    icon = config.get(CONF_ICON)
    _LOGGER.debug("latitude=%s, longitude=%s, url=%s, radius=%s, "
                  "scan_interval=%s", home_latitude, home_longitude, url,
                  radius_in_km, scan_interval)
    # Instantiate feed manager for the configured feed.
    manager = GeoRssFeedManager(hass, add_devices, storage, scan_interval,
                                name, home_latitude, home_longitude, url,
                                radius_in_km, categories,
                                attributes_definition, filters_definition,
                                icon)
    return True


class GeoRssFeedManager(FeedManager):
    """Feed Manager for Geo RSS feeds."""

    def __init__(self, hass, add_devices, storage, scan_interval, name,
                 home_latitude, home_longitude, url, radius_in_km, categories,
                 attributes_definition, filters_definition, icon):
        """Initialize the GeoRSS Feed Manager."""
        self._scan_interval = scan_interval
        super().__init__(url, scan_interval, None, hass, storage)
        self._add_devices = add_devices
        self._name = name
        self._home_coordinates = [home_latitude, home_longitude]
        self._geo_distance_helper = GeoDistanceHelper(self._home_coordinates)
        self._radius_in_km = radius_in_km
        self._categories = categories
        self._attributes_definition = attributes_definition
        self._attributes_names = []
        for definition in attributes_definition:
            self._attributes_names.append(definition[CONF_ATTRIBUTES_NAME])
        self._filters_definition = filters_definition
        self._icon = icon
        entity_id = generate_entity_id('{}', name, hass=hass)
        self._event_type = entity_id
        self._feed_id = entity_id
        self._managed_devices = []
        self.group = None

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def feed_entries(self):
        """Return the current set of feed entries."""
        return [] if not hasattr(self._feed, 'entries') else self._feed.entries

    def _init_regular_updates(self, hass):
        """Schedule regular updates based on configured time interval."""
        track_time_interval(hass, lambda now: self._update(),
                            self._scan_interval)

    def _calculate_distance(self, entry):
        """Determine geometry data from entry and calculate distance."""
        geometry = None
        if hasattr(entry, 'where'):
            geometry = entry.where
        elif hasattr(entry, 'geo_lat') and hasattr(entry, 'geo_long'):
            coordinates = (float(entry.geo_long), float(entry.geo_lat))
            point = namedtuple('Point', ['type', 'coordinates'])
            geometry = point('Point', coordinates)
        if geometry:
            return geometry, self._geo_distance_helper.distance_to_geometry(
                geometry)
        else:
            return geometry, None

    def _matches_category(self, entry):
        if self._categories:
            if hasattr(entry, 'category'):
                return entry.category in self._categories
            else:
                # Entry has no category.
                return False
        else:
            # No categories defined - always match.
            return True

    def _filter_entries(self):
        """Filter entries by distance from home coordinates."""
        available_entries = self._feed.entries
        keep_entries = []
        for entry in available_entries:
            # Filter by category.
            if self._matches_category(entry):
                # Filter by distance.
                geometry, distance = self._calculate_distance(entry)
                if distance <= self._radius_in_km:
                    # Add distance value as a new attribute
                    entry.update({ATTR_DISTANCE: distance})
                    entry.update({ATTR_GEOMETRY: geometry})
                    # Compute custom attributes.
                    for definition in self._attributes_definition:
                        if hasattr(entry, definition[CONF_ATTRIBUTES_SOURCE]):
                            # Use 'search' to allow for matching anywhere in
                            # the source attribute.
                            match = re.search(
                                definition[CONF_ATTRIBUTES_REGEXP],
                                entry[definition[CONF_ATTRIBUTES_SOURCE]])
                            entry.update({definition[CONF_ATTRIBUTES_NAME]:
                                         '' if not match else match.group(
                                                  CONF_CUSTOM_ATTRIBUTE)})
                        else:
                            _LOGGER.warning("No attribute '%s' found",
                                            definition[CONF_ATTRIBUTES_SOURCE])
                            # Add empty string to allow for applying filter
                            # rules.
                            entry.update(
                                {definition[CONF_ATTRIBUTES_NAME]: ''})
                    # Run custom filters if defined.
                    keep_entry = True
                    if self._filters_definition:
                        for definition in self._filters_definition:
                            if hasattr(entry, definition[
                                    CONF_FILTERS_ATTRIBUTE]):
                                match = re.match(
                                    definition[CONF_FILTERS_REGEXP],
                                    entry.get(
                                        definition[CONF_FILTERS_ATTRIBUTE]))
                                # If the attribute does not match, immediately
                                # drop out of loop to eliminate the entry.
                                if not match:
                                    _LOGGER.debug(
                                        "Entry %s does not match filter %s",
                                        entry, definition)
                                    keep_entry = False
                                    break
                            else:
                                # Discard entry because it does not contain
                                # attribute
                                _LOGGER.debug(
                                    "Entry %s does not contain attribute %s",
                                    entry, definition[CONF_FILTERS_ATTRIBUTE])
                                keep_entry = False
                                break
                    if keep_entry:
                        keep_entries.append(entry)
        _LOGGER.debug("%s entries found nearby after filtering",
                      len(keep_entries))
        self._feed.entries = keep_entries

    def _update(self):
        """Update the feed and then update connected devices."""
        super()._update()
        if self._last_update_successful:
            # Update existing and remove obsolete devices.
            remaining_entries = self._update_or_remove_devices()
            # Add new devices.
            self._generate_new_devices(remaining_entries)
            # Group all devices.
            self._group_devices()

    def _group_devices(self):
        """Re-group all entities"""
        if not self.group:
            self.group = self._hass.components.group
        self.group.set_group(
            util.slugify(self._name), visible=True,
            name=self._name, entity_ids=[device.entity_id for device
                                         in self._managed_devices])

    def _generate_new_devices(self, entries):
        """Generate new entities for events that have occurred for the first
           time"""
        new_devices = []
        for entry in entries:
            distance, latitude, longitude, external_id, name, category, \
                custom_attributes = self._extract_data(entry)
            entity_id = generate_entity_id(ENTITY_ID_FORMAT,
                                           self._name + '_'
                                           + entry.get(ATTR_TITLE),
                                           hass=self._hass)
            new_device = GeoRssLocationEvent(self._hass, entity_id, distance,
                                             latitude, longitude, external_id,
                                             name, category, self._icon,
                                             custom_attributes)
            _LOGGER.debug("New device added %s", new_device)
            new_devices.append(new_device)
        self._add_devices(new_devices)
        self._managed_devices.extend(new_devices)

    def _extract_data(self, entry):
        """Extract relevant data from the external event."""
        geometry = entry.get(ATTR_GEOMETRY)
        if geometry.type == 'Point':
            latitude, longitude = geometry.coordinates[1], \
                                  geometry.coordinates[0]
        elif geometry.type == 'Polygon':
            # TODO: find the center of polygon?
            latitude, longitude = geometry.coordinates[0][0][1], \
                                  geometry.coordinates[0][0][0]
        else:
            latitude, longitude = None, None
        custom_attributes = {}
        for name in self._attributes_names:
            custom_attributes[name] = entry[name]
        return entry.get(ATTR_DISTANCE), latitude, longitude, \
            entry.get(ATTR_ID), entry.get(ATTR_TITLE), \
            entry.get(ATTR_CATEGORY), custom_attributes

    def _update_or_remove_devices(self):
        """Update existing devices with new incoming data and remove devices
           if feed does not contain corresponding entry anymore."""
        entries = self._feed.entries
        remove_entry = None
        # Remove obsolete entities for events that have disappeared
        for device in self._managed_devices:
            # Remove entry from previous iteration - if applicable.
            if remove_entry:
                entries.remove(remove_entry)
                remove_entry = None
            for entry in entries:
                entry_id = entry.get(ATTR_ID)
                if device.external_id == entry_id:
                    # Existing device - update details.
                    _LOGGER.debug("Existing device found %s", device)
                    remove_entry = entry
                    # Update existing device's details with event data.
                    distance, latitude, longitude, external_id, name, \
                        category, custom_attributes = self._extract_data(entry)
                    device.distance = distance
                    device.latitude = latitude
                    device.longitude = longitude
                    device.name = name
                    device.category = category
                    device.custom_attributes = custom_attributes
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


class GeoDistanceHelper(object):
    """Helper to calculate distances between geometries."""

    def __init__(self, home_coordinates):
        """Initialize the geo distance helper."""
        self._home_coordinates = home_coordinates

    def distance_to_geometry(self, geometry):
        """Calculate the distance between HA's home coordinates and the
        provided geometry."""
        distance = float("inf")
        if geometry.type == 'Point':
            distance = self._distance_to_point(geometry)
        elif geometry.type == 'Polygon':
            distance = self._distance_to_polygon(geometry.coordinates[0])
        else:
            _LOGGER.warning("Not yet implemented: %s", geometry.type)
        return distance

    def _distance_to_point(self, point):
        """Calculate the distance between HA and the provided point."""
        # Swap coordinates to match: (lat, lon).
        coordinates = (point.coordinates[1], point.coordinates[0])
        return self._distance_to_coords(coordinates)

    def _distance_to_coords(self, coordinates):
        """Calculate the distance between HA and the provided coordinates."""
        # Expecting coordinates in format: (lat, lon).
        from haversine import haversine
        distance = haversine(coordinates, self._home_coordinates)
        _LOGGER.debug("Distance from %s to %s: %s km", self._home_coordinates,
                      coordinates, distance)
        return distance

    def _distance_to_polygon(self, polygon):
        """Calculate the distance between HA and the provided polygon."""
        distance = float("inf")
        # Calculate distance from polygon by calculating the distance
        # to each point of the polygon but not to each edge of the
        # polygon; should be good enough
        for polygon_point in polygon:
            coordinates = (polygon_point[1], polygon_point[0])
            distance = min(distance, self._distance_to_coords(coordinates))
        _LOGGER.debug("Distance from %s to %s: %s km", self._home_coordinates,
                      polygon, distance)
        return distance


class GeoRssLocationEvent(GeoLocationEvent):
    """This represents an external event with GeoRSS data."""

    def __init__(self, hass, entity_id, distance, latitude, longitude,
                 external_id, name, category, icon, custom_attributes):
        """Initialize entity with data provided."""
        super().__init__(hass, entity_id, distance, latitude, longitude, icon)
        self._external_id = external_id
        self._name = name
        self._category = category
        self._custom_attributes = custom_attributes

    @property
    def external_id(self):
        """Return external id of this event."""
        return self._external_id

    @property
    def name(self):
        """Return the name of the event."""
        return self._name

    @name.setter
    def name(self, value):
        """Set event's name."""
        self._name = value

    @property
    def category(self):
        """Return the category of the event."""
        return self._category

    @category.setter
    def category(self, value):
        """Set event's category."""
        self._category = value

    @property
    def custom_attributes(self):
        """Return the custom attributes of the event."""
        return self._custom_attributes

    @custom_attributes.setter
    def custom_attributes(self, value):
        """Set event's custom attributes."""
        self._custom_attributes = value

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = super().device_state_attributes
        attributes.update({'external id': self._external_id,
                           'category': self._category})
        attributes.update(self._custom_attributes)
        return attributes
