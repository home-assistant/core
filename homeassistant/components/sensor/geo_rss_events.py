"""
Generic GeoRSS events service.

Retrieves current events (typically incidents or alerts) in GeoRSS format, and
shows information on events filtered by distance to the HA instance's location
and grouped by category.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.geo_rss_events/
"""

import logging
from collections import namedtuple
from datetime import timedelta
from functools import total_ordering
import re

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (STATE_UNKNOWN, CONF_UNIT_OF_MEASUREMENT,
                                 CONF_NAME)
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.util import Throttle

REQUIREMENTS = ['feedparser==5.2.1', 'haversine==0.4.5']

_LOGGER = logging.getLogger(__name__)

ATTR_CATEGORY = 'category'
ATTR_DATE_PUBLISHED = 'date_published'
ATTR_DATE_UPDATED = 'date_updated'
ATTR_DISTANCE = 'distance'
ATTR_ID = 'id'
ATTR_TITLE = 'title'
VALID_SORT_BY = [ATTR_DATE_PUBLISHED, ATTR_DATE_UPDATED, ATTR_DISTANCE,
                 ATTR_TITLE]

CONF_CATEGORIES = 'categories'
CONF_CUSTOM_ATTRIBUTES = 'custom_attributes'
CONF_CUSTOM_ATTRIBUTES_NAME = 'name'
CONF_CUSTOM_ATTRIBUTES_REGEXP = 'regexp'
CONF_CUSTOM_ATTRIBUTES_SOURCE = 'source'
CONF_CUSTOM_FILTERS = 'custom_filters'
CONF_CUSTOM_FILTERS_ATTRIBUTE = 'attribute'
CONF_CUSTOM_FILTERS_REGEXP = 'regexp'
CONF_PUBLISH_EVENTS = 'publish_events'
CONF_RADIUS = 'radius'
CONF_SORT_BY = 'sort_by'
CONF_SORT_REVERSE = 'sort_reverse'
CONF_URL = 'url'

DEFAULT_ICON = 'mdi:alert'
DEFAULT_NAME = "Event Service"
DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_UNIT_OF_MEASUREMENT = 'Events'

DOMAIN = 'geo_rss_events'

# Minimum time between updates from the source.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

SCAN_INTERVAL = timedelta(minutes=5)

CUSTOM_ATTRIBUTES_SCHEMA = vol.Schema({
    vol.Required(CONF_CUSTOM_ATTRIBUTES_NAME): cv.string,
    vol.Required(CONF_CUSTOM_ATTRIBUTES_SOURCE): cv.string,
    vol.Required(CONF_CUSTOM_ATTRIBUTES_REGEXP): cv.string,
})

CUSTOM_FILTERS_SCHEMA = vol.Schema({
    vol.Required(CONF_CUSTOM_FILTERS_ATTRIBUTE): cv.string,
    vol.Required(CONF_CUSTOM_FILTERS_REGEXP): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CATEGORIES, default=[]): vol.All(cv.ensure_list,
                                                       [cv.string]),
    vol.Optional(CONF_CUSTOM_ATTRIBUTES,
                 default=[]): vol.All(cv.ensure_list,
                                      [CUSTOM_ATTRIBUTES_SCHEMA]),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT,
                 default=DEFAULT_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_SORT_BY, default=None): cv.string,
    vol.Optional(CONF_SORT_REVERSE, default=False): cv.boolean,
    vol.Optional(CONF_CUSTOM_FILTERS,
                 default=[]): vol.All(cv.ensure_list,
                                      [CUSTOM_FILTERS_SCHEMA]),
    vol.Optional(CONF_PUBLISH_EVENTS, default=False): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the GeoRSS component."""
    # Grab location from config
    home_latitude = hass.config.latitude
    home_longitude = hass.config.longitude
    url = config.get(CONF_URL)
    radius_in_km = config.get(CONF_RADIUS)
    name = config.get(CONF_NAME)
    categories = config.get(CONF_CATEGORIES)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    sort_by = config.get(CONF_SORT_BY)
    sort_reverse = config.get(CONF_SORT_REVERSE)
    custom_attributes_definition = config.get(CONF_CUSTOM_ATTRIBUTES)
    custom_filters_definition = config.get(CONF_CUSTOM_FILTERS)
    publish_events = config.get(CONF_PUBLISH_EVENTS)

    _LOGGER.debug("latitude=%s, longitude=%s, url=%s, radius=%s",
                  home_latitude, home_longitude, url, radius_in_km)

    # Initialise update service.
    data = GeoRssServiceData(home_latitude, home_longitude, url, radius_in_km,
                             custom_attributes_definition,
                             custom_filters_definition)
    data.update()

    # Create all sensors based on categories.
    devices = []
    if not categories:
        device = GeoRssServiceSensor(hass, None, data, name,
                                     unit_of_measurement, sort_by,
                                     sort_reverse, publish_events)
        devices.append(device)
    else:
        for category in categories:
            device = GeoRssServiceSensor(hass, category, data, name,
                                         unit_of_measurement, sort_by,
                                         sort_reverse, publish_events)
            devices.append(device)
    add_devices(devices, True)


@total_ordering
class MinType(object):
    """Represents an object type that is smaller than another when sorting."""

    def __le__(self, other):
        return True

    def __eq__(self, other):
        return self is other


class GeoRssServiceSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, category, data, service_name, unit_of_measurement,
                 sort_by, sort_reverse, publish_events):
        """Initialize the sensor."""
        self.hass = hass
        self._category = category
        self._data = data
        self._service_name = service_name
        self._state = STATE_UNKNOWN
        self._state_attributes = None
        self._unit_of_measurement = unit_of_measurement
        self._sort_by = sort_by
        self._sort_reverse = sort_reverse
        self._publish_events = publish_events
        self._event_type_id = generate_entity_id('{}', service_name, hass=hass)
        self._previous_events = []

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._service_name,
                              'Any' if self._category is None
                              else self._category)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the default icon to use in the frontend."""
        return DEFAULT_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._state_attributes

    def update(self):
        """Update this sensor from the GeoRSS service."""
        _LOGGER.debug("About to update sensor %s", self.entity_id)
        self._data.update()
        # If no events were found due to an error then just set state to zero.
        if self._data.events is None:
            self._state = 0
        else:
            # Split up events by category (if defined).
            if self._category is None:
                # Add all events regardless of category.
                my_events = self._data.events
            else:
                # Only keep events that belong to sensor's category.
                my_events = [event for event in self._data.events if
                             event[ATTR_CATEGORY] == self._category]
            _LOGGER.debug("Adding events to sensor %s: %s", self.entity_id,
                          my_events)
            self._state = len(my_events)
            # Sort events if configured to do so.
            if self._sort_by is not None:
                min_object = MinType()
                my_events = sorted(my_events,
                                   key=lambda event:
                                   min_object if self._sort_by not in event or
                                                 event[self._sort_by] is None
                                   else event[self._sort_by],
                                   reverse=self._sort_reverse)
            # And now compute the attributes from the filtered events.
            matrix = {}
            for event in my_events:
                matrix[event[ATTR_TITLE]] = '{:.0f}km'.format(
                    event[ATTR_DISTANCE])
            self._state_attributes = matrix
            # Finally publish new events to the bus.
            if self._publish_events:
                events_to_publish = self.filter_events_to_publish(my_events)
                _LOGGER.debug("New events to publish: %s", events_to_publish)
                self.publish_events(events_to_publish)
            self._previous_events = my_events

    def filter_events_to_publish(self, events):
        """Publish new or updated events, or all if this is the first call."""
        if not self._previous_events:
            # Publish all events.
            return events
        else:
            # Find new or changed events
            new_events = []
            for event in events:
                include_event = True
                for previous_event in self._previous_events:
                    if event[ATTR_ID] == previous_event[ATTR_ID]:
                        # Check the update date.
                        if hasattr(event, ATTR_DATE_UPDATED):
                            if hasattr(previous_event,
                                       ATTR_DATE_UPDATED):
                                if event[ATTR_DATE_UPDATED] <= \
                                        previous_event[ATTR_DATE_UPDATED]:
                                    # Event has not been updated.
                                    include_event = False
                        else:
                            # Event with same id but not updated found.
                            include_event = False
                if include_event:
                    new_events.append(event)
            return new_events

    def publish_events(self, events):
        """Publish the provided events as HA events to the bus."""
        for event in events:
            self.hass.bus.fire(self._event_type_id, event)


class GeoRssServiceData(object):
    """Provides access to GeoRSS feed and stores the latest data."""

    def __init__(self, home_latitude, home_longitude, url, radius_in_km,
                 custom_attributes_definition, custom_filters_definition):
        """Initialize the update service."""
        self._home_coordinates = [home_latitude, home_longitude]
        self._url = url
        self._radius_in_km = radius_in_km
        self._custom_attributes_definition = custom_attributes_definition
        self._custom_filters_definition = custom_filters_definition
        self.events = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Retrieve data from GeoRSS feed and store events."""
        import feedparser
        feed_data = feedparser.parse(self._url)
        if not feed_data:
            _LOGGER.error("Error fetching feed data from %s", self._url)
        else:
            events = self.filter_entries(feed_data)
            self.events = events

    def filter_entries(self, feed_data):
        """Filter entries by distance from home coordinates."""
        events = []
        _LOGGER.debug("%s entri(es) available in feed %s",
                      len(feed_data.entries), self._url)
        for entry in feed_data.entries:
            geometry = None
            if hasattr(entry, 'where'):
                geometry = entry.where
            elif hasattr(entry, 'geo_lat') and hasattr(entry, 'geo_long'):
                coordinates = (float(entry.geo_long), float(entry.geo_lat))
                point = namedtuple('Point', ['type', 'coordinates'])
                geometry = point('Point', coordinates)
            if geometry:
                distance = self.calculate_distance_to_geometry(geometry)
                if distance <= self._radius_in_km:
                    event = self.create_event(entry, distance)
                    if event:
                        events.append(event)
        _LOGGER.debug("%s events found nearby", len(events))
        return events

    def create_event(self, entry, distance):
        # Create the event with attributes.
        event = {
            ATTR_CATEGORY: None if not hasattr(
                entry, 'category') else entry.category,
            ATTR_TITLE: None if not hasattr(
                entry, 'title') else entry.title,
            ATTR_DATE_PUBLISHED: None if not hasattr(
                entry,
                'published_parsed') else entry.published_parsed,
            ATTR_DATE_UPDATED: None if not hasattr(
                entry, 'updated_parsed') else entry.updated_parsed,
            ATTR_DISTANCE: distance,
            ATTR_ID: None if not hasattr(entry, 'id') else entry.id
        }
        # Compute custom attributes.
        for definition in self._custom_attributes_definition:
            if hasattr(entry,
                       definition[CONF_CUSTOM_ATTRIBUTES_SOURCE]):
                match = re.match(definition[CONF_CUSTOM_ATTRIBUTES_REGEXP],
                                 entry[definition[
                                     CONF_CUSTOM_ATTRIBUTES_SOURCE]])
                event[definition[
                    CONF_CUSTOM_ATTRIBUTES_NAME]] = None if not match \
                    else match.group('custom_attribute')
            else:
                _LOGGER.warning("No attribute '%s' found",
                                definition[CONF_CUSTOM_ATTRIBUTES_SOURCE])
                event[definition['name']] = None
        # Run custom filters if defined.
        if self._custom_filters_definition:
            for definition in self._custom_filters_definition:
                if definition[CONF_CUSTOM_FILTERS_ATTRIBUTE] in event:
                    match = re.match(definition[CONF_CUSTOM_FILTERS_REGEXP],
                                     event[definition[
                                         CONF_CUSTOM_FILTERS_ATTRIBUTE]])
                    # If the attribute does not match, immediately return
                    # None value to eliminate entry, otherwise continue with
                    # the filter loop.
                    if not match:
                        _LOGGER.debug("Event %s does not match filter %s",
                                      event, definition)
                        return None
        _LOGGER.debug("Keeping event %s", event)
        return event

    def calculate_distance_to_geometry(self, geometry):
        """Calculate the distance between HA and provided geometry."""
        distance = float("inf")
        if geometry.type == 'Point':
            distance = self.calculate_distance_to_point(geometry)
        elif geometry.type == 'Polygon':
            distance = self.calculate_distance_to_polygon(
                geometry.coordinates[0])
        else:
            _LOGGER.warning("Not yet implemented: %s", geometry.type)
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
        for polygon_point in polygon:
            coordinates = (polygon_point[1], polygon_point[0])
            distance = min(distance,
                           self.calculate_distance_to_coords(coordinates))
        _LOGGER.debug("Distance from %s to %s: %s km", self._home_coordinates,
                      polygon, distance)
        return distance
