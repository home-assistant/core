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
from typing import Optional

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.geo_location import GeoLocationEvent
from homeassistant.const import CONF_RADIUS, CONF_URL, CONF_SCAN_INTERVAL, \
    EVENT_HOMEASSISTANT_START
from homeassistant.components.geo_location import PLATFORM_SCHEMA
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['geojson_client==0.1']

_LOGGER = logging.getLogger(__name__)

ATTR_EXTERNAL_ID = 'external_id'

DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_UNIT_OF_MEASUREMENT = "km"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM):
        vol.Coerce(float),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the GeoJSON Events platform."""
    url = config[CONF_URL]
    scan_interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    radius_in_km = config[CONF_RADIUS]
    # Initialize the entity manager.
    GeoJsonFeedManager(hass, add_entities, scan_interval, url, radius_in_km)


class GeoJsonFeedManager:
    """Feed Manager for GeoJSON feeds."""

    def __init__(self, hass, add_entities, scan_interval, url, radius_in_km):
        """Initialize the GeoJSON Feed Manager."""
        from geojson_client.generic_feed import GenericFeed
        self._hass = hass
        self._feed = GenericFeed((hass.config.latitude, hass.config.longitude),
                                 filter_radius=radius_in_km, url=url)
        self._add_entities = add_entities
        self._scan_interval = scan_interval
        self._feed_entries = []
        self._managed_entities = []
        hass.bus.listen_once(
            EVENT_HOMEASSISTANT_START, lambda _: self._update())
        self._init_regular_updates()

    def _init_regular_updates(self):
        """Schedule regular updates at the specified interval."""
        track_time_interval(self._hass, lambda now: self._update(),
                            self._scan_interval)

    def _update(self):
        """Update the feed and then update connected entities."""
        import geojson_client
        status, feed_entries = self._feed.update()
        if status == geojson_client.UPDATE_OK:
            _LOGGER.debug("Data retrieved %s", feed_entries)
            # Keep a copy of all feed entries for future lookups by entities.
            self._feed_entries = feed_entries.copy()
            keep_entries = self._update_or_remove_entities(feed_entries)
            self._generate_new_entities(keep_entries)
        elif status == geojson_client.UPDATE_OK_NO_DATA:
            _LOGGER.debug("Update successful, but no data received from %s",
                          self._feed)
        else:
            _LOGGER.warning("Update not successful, no data received from %s",
                            self._feed)
            # Remove all entities.
            self._update_or_remove_entities([])

    def _update_or_remove_entities(self, feed_entries):
        """Update existing entries and remove obsolete entities."""
        _LOGGER.debug("Entries for updating: %s", feed_entries)
        remove_entry = None
        # Remove obsolete entities for events that have disappeared
        managed_entities = self._managed_entities.copy()
        for entity in managed_entities:
            # Remove entry from previous iteration - if applicable.
            if remove_entry:
                feed_entries.remove(remove_entry)
                remove_entry = None
            for entry in feed_entries:
                if entity.external_id == entry.external_id:
                    # Existing entity - update details.
                    _LOGGER.debug("Existing entity found %s", entity)
                    remove_entry = entry
                    entity.schedule_update_ha_state(True)
                    break
            else:
                # Remove obsolete entity.
                _LOGGER.debug("Entity not current anymore %s", entity)
                self._managed_entities.remove(entity)
                self._hass.add_job(entity.async_remove())
        # Remove entry from very last iteration - if applicable.
        if remove_entry:
            feed_entries.remove(remove_entry)
        # Return the remaining entries that new entities must be created for.
        return feed_entries

    def _generate_new_entities(self, entries):
        """Generate new entities for events."""
        new_entities = []
        for entry in entries:
            new_entity = GeoJsonLocationEvent(self, entry)
            _LOGGER.debug("New entity added %s", new_entity)
            new_entities.append(new_entity)
        # Add new entities to HA and keep track of them in this manager.
        self._add_entities(new_entities, True)
        self._managed_entities.extend(new_entities)

    def get_feed_entry(self, external_id):
        """Return a feed entry identified by external id."""
        return next((entry for entry in self._feed_entries
                     if entry.external_id == external_id), None)


class GeoJsonLocationEvent(GeoLocationEvent):
    """This represents an external event with GeoJSON data."""

    def __init__(self, feed_manager, feed_entry):
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._update_from_feed(feed_entry)

    @property
    def should_poll(self):
        """No polling needed for GeoJSON location events."""
        return False

    async def async_update(self):
        """Update this entity from the data held in the feed manager."""
        feed_entry = self._feed_manager.get_feed_entry(self.external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(self, feed_entry):
        """Update the internal state from the provided feed entry."""
        self._name = feed_entry.title
        self._distance = feed_entry.distance_to_home
        self._latitude = feed_entry.coordinates[0]
        self._longitude = feed_entry.coordinates[1]
        self.external_id = feed_entry.external_id

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._name

    @property
    def distance(self) -> Optional[float]:
        """Return distance value of this external event."""
        return self._distance

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return DEFAULT_UNIT_OF_MEASUREMENT

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        if self.external_id:
            attributes[ATTR_EXTERNAL_ID] = self.external_id
        return attributes
