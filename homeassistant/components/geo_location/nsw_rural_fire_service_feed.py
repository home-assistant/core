"""
NSW Rural Fire Service Feed platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/geo_location/nsw_rural_fire_service_feed/
"""
from datetime import timedelta
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.components.geo_location import (
    PLATFORM_SCHEMA, GeoLocationEvent)
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_LOCATION, CONF_RADIUS, CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['geojson_client==0.3']

_LOGGER = logging.getLogger(__name__)

ATTR_CATEGORY = 'category'
ATTR_COUNCIL_AREA = 'council_area'
ATTR_EXTERNAL_ID = 'external_id'
ATTR_FIRE = 'fire'
ATTR_PUBLICATION_DATE = 'publication_date'
ATTR_RESPONSIBLE_AGENCY = 'responsible_agency'
ATTR_SIZE = 'size'
ATTR_STATUS = 'status'
ATTR_TYPE = 'type'

CONF_CATEGORIES = 'categories'

DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_UNIT_OF_MEASUREMENT = 'km'

SCAN_INTERVAL = timedelta(minutes=5)

SIGNAL_DELETE_ENTITY = 'nsw_rural_fire_service_feed_delete_{}'
SIGNAL_UPDATE_ENTITY = 'nsw_rural_fire_service_feed_update_{}'

SOURCE = 'nsw_rural_fire_service_feed'

VALID_CATEGORIES = [
    'Advice',
    'Emergency Warning',
    'Not Applicable',
    'Watch and Act',
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CATEGORIES, default=[]):
        vol.All(cv.ensure_list, [vol.In(VALID_CATEGORIES)]),
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NSW Rural Fire Service Feed platform."""
    scan_interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    coordinates = (config.get(CONF_LATITUDE, hass.config.latitude),
                   config.get(CONF_LONGITUDE, hass.config.longitude))
    radius_in_km = config[CONF_RADIUS]
    categories = config.get(CONF_CATEGORIES)
    # Initialize the entity manager.
    feed = NswRuralFireServiceFeedEntityManager(
        hass, add_entities, scan_interval, coordinates, radius_in_km,
        categories)

    def start_feed_manager(event):
        """Start feed manager."""
        feed.startup()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_feed_manager)


class NswRuralFireServiceFeedEntityManager:
    """Feed Entity Manager for NSW Rural Fire Service GeoJSON feed."""

    def __init__(self, hass, add_entities, scan_interval, coordinates,
                 radius_in_km, categories):
        """Initialize the Feed Entity Manager."""
        from geojson_client.nsw_rural_fire_service_feed \
            import NswRuralFireServiceFeedManager

        self._hass = hass
        self._feed_manager = NswRuralFireServiceFeedManager(
            self._generate_entity, self._update_entity, self._remove_entity,
            coordinates, filter_radius=radius_in_km,
            filter_categories=categories)
        self._add_entities = add_entities
        self._scan_interval = scan_interval

    def startup(self):
        """Start up this manager."""
        self._feed_manager.update()
        self._init_regular_updates()

    def _init_regular_updates(self):
        """Schedule regular updates at the specified interval."""
        track_time_interval(
            self._hass, lambda now: self._feed_manager.update(),
            self._scan_interval)

    def get_entry(self, external_id):
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    def _generate_entity(self, external_id):
        """Generate new entity."""
        new_entity = NswRuralFireServiceLocationEvent(self, external_id)
        # Add new entities to HA.
        self._add_entities([new_entity], True)

    def _update_entity(self, external_id):
        """Update entity."""
        dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(external_id))

    def _remove_entity(self, external_id):
        """Remove entity."""
        dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(external_id))


class NswRuralFireServiceLocationEvent(GeoLocationEvent):
    """This represents an external event with NSW Rural Fire Service data."""

    def __init__(self, feed_manager, external_id):
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._name = None
        self._distance = None
        self._latitude = None
        self._longitude = None
        self._attribution = None
        self._category = None
        self._publication_date = None
        self._location = None
        self._council_area = None
        self._status = None
        self._type = None
        self._fire = None
        self._size = None
        self._responsible_agency = None
        self._remove_signal_delete = None
        self._remove_signal_update = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass, SIGNAL_DELETE_ENTITY.format(self._external_id),
            self._delete_callback)
        self._remove_signal_update = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ENTITY.format(self._external_id),
            self._update_callback)

    @callback
    def _delete_callback(self):
        """Remove this entity."""
        self._remove_signal_delete()
        self._remove_signal_update()
        self.hass.async_create_task(self.async_remove())

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed for NSW Rural Fire Service location events."""
        return False

    async def async_update(self):
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(self, feed_entry):
        """Update the internal state from the provided feed entry."""
        self._name = feed_entry.title
        self._distance = feed_entry.distance_to_home
        self._latitude = feed_entry.coordinates[0]
        self._longitude = feed_entry.coordinates[1]
        self._attribution = feed_entry.attribution
        self._category = feed_entry.category
        self._publication_date = feed_entry.publication_date
        self._location = feed_entry.location
        self._council_area = feed_entry.council_area
        self._status = feed_entry.status
        self._type = feed_entry.type
        self._fire = feed_entry.fire
        self._size = feed_entry.size
        self._responsible_agency = feed_entry.responsible_agency

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return SOURCE

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
        for key, value in (
                (ATTR_EXTERNAL_ID, self._external_id),
                (ATTR_CATEGORY, self._category),
                (ATTR_LOCATION, self._location),
                (ATTR_ATTRIBUTION, self._attribution),
                (ATTR_PUBLICATION_DATE, self._publication_date),
                (ATTR_COUNCIL_AREA, self._council_area),
                (ATTR_STATUS, self._status),
                (ATTR_TYPE, self._type),
                (ATTR_FIRE, self._fire),
                (ATTR_SIZE, self._size),
                (ATTR_RESPONSIBLE_AGENCY, self._responsible_agency),
        ):
            if value or isinstance(value, bool):
                attributes[key] = value
        return attributes
