"""Geolocation support for GeoNet NZ Quakes Feeds."""
from datetime import timedelta
import logging
from typing import Optional

from aio_geojson_geonetnz_quakes import GeonetnzQuakesFeedManager

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    ATTR_TIME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from .const import CONF_MINIMUM_MAGNITUDE, CONF_MMI, DOMAIN, FEED

_LOGGER = logging.getLogger(__name__)

ATTR_DEPTH = "depth"
ATTR_EXTERNAL_ID = "external_id"
ATTR_LOCALITY = "locality"
ATTR_MAGNITUDE = "magnitude"
ATTR_MMI = "mmi"
ATTR_PUBLICATION_DATE = "publication_date"
ATTR_QUALITY = "quality"

DEFAULT_FILTER_TIME_INTERVAL = timedelta(days=7)

SIGNAL_DELETE_ENTITY = "geonetnz_quakes_delete_{}"
SIGNAL_UPDATE_ENTITY = "geonetnz_quakes_update_{}"

SOURCE = "geonetnz_quakes"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the GeoNet NZ Quakes Feed platform."""
    radius = entry.data[CONF_RADIUS]
    unit_system = entry.data[CONF_UNIT_SYSTEM]
    if unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
        radius = METRIC_SYSTEM.length(radius, LENGTH_MILES)
    manager = GeonetnzQuakesFeedEntityManager(
        hass,
        async_add_entities,
        entry.data[CONF_SCAN_INTERVAL],
        entry.data[CONF_LATITUDE],
        entry.data[CONF_LONGITUDE],
        entry.data[CONF_MMI],
        radius,
        unit_system,
        entry.data[CONF_MINIMUM_MAGNITUDE],
    )
    hass.data[DOMAIN][FEED][entry.entry_id] = manager
    await manager.async_init()


class GeonetnzQuakesFeedEntityManager:
    """Feed Entity Manager for GeoNet NZ Quakes feed."""

    def __init__(
        self,
        hass,
        async_add_entities,
        scan_interval,
        latitude,
        longitude,
        mmi,
        radius_in_km,
        unit_system,
        minimum_magnitude,
    ):
        """Initialize the Feed Entity Manager."""
        self._hass = hass
        coordinates = (latitude, longitude)
        websession = aiohttp_client.async_get_clientsession(hass)
        self._feed_manager = GeonetnzQuakesFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            mmi=mmi,
            filter_radius=radius_in_km,
            filter_minimum_magnitude=minimum_magnitude,
            filter_time=DEFAULT_FILTER_TIME_INTERVAL,
        )
        self._async_add_entities = async_add_entities
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unit_system = unit_system
        self._track_time_remove_callback = None

    async def async_init(self):
        """Schedule regular updates based on configured time interval."""

        async def update(event_time):
            """Update."""
            await self.async_update()

        await self.async_update()
        self._track_time_remove_callback = async_track_time_interval(
            self._hass, update, self._scan_interval
        )
        _LOGGER.debug("Feed entity manager initialized")

    async def async_update(self):
        """Refresh data."""
        await self._feed_manager.update()
        _LOGGER.debug("Feed entity manager updated")

    async def async_stop(self):
        """Stop this feed entity manager from refreshing."""
        if self._track_time_remove_callback:
            self._track_time_remove_callback()
        _LOGGER.debug("Feed entity manager stopped")

    def get_entry(self, external_id):
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    async def _generate_entity(self, external_id):
        """Generate new entity."""
        new_entity = GeonetnzQuakesEvent(self, external_id, self._unit_system)
        # Add new entities to HA.
        self._async_add_entities([new_entity], True)

    async def _update_entity(self, external_id):
        """Update entity."""
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(external_id))

    async def _remove_entity(self, external_id):
        """Remove entity."""
        async_dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(external_id))


class GeonetnzQuakesEvent(GeolocationEvent):
    """This represents an external event with GeoNet NZ Quakes feed data."""

    def __init__(self, feed_manager, external_id, unit_system):
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._unit_system = unit_system
        self._title = None
        self._distance = None
        self._latitude = None
        self._longitude = None
        self._attribution = None
        self._depth = None
        self._locality = None
        self._magnitude = None
        self._mmi = None
        self._quality = None
        self._time = None
        self._remove_signal_delete = None
        self._remove_signal_update = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            SIGNAL_DELETE_ENTITY.format(self._external_id),
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            SIGNAL_UPDATE_ENTITY.format(self._external_id),
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        self._remove_signal_delete()
        self._remove_signal_update()

    @callback
    def _delete_callback(self):
        """Remove this entity."""
        self.hass.async_create_task(self.async_remove())

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed for GeoNet NZ Quakes feed location events."""
        return False

    async def async_update(self):
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(self, feed_entry):
        """Update the internal state from the provided feed entry."""
        self._title = feed_entry.title
        # Convert distance if not metric system.
        if self._unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
            self._distance = IMPERIAL_SYSTEM.length(
                feed_entry.distance_to_home, LENGTH_KILOMETERS
            )
        else:
            self._distance = feed_entry.distance_to_home
        self._latitude = feed_entry.coordinates[0]
        self._longitude = feed_entry.coordinates[1]
        self._attribution = feed_entry.attribution
        self._depth = feed_entry.depth
        self._locality = feed_entry.locality
        self._magnitude = feed_entry.magnitude
        self._mmi = feed_entry.mmi
        self._quality = feed_entry.quality
        self._time = feed_entry.time

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:pulse"

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return SOURCE

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._title

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
        if self._unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._external_id),
            (ATTR_ATTRIBUTION, self._attribution),
            (ATTR_DEPTH, self._depth),
            (ATTR_LOCALITY, self._locality),
            (ATTR_MAGNITUDE, self._magnitude),
            (ATTR_MMI, self._mmi),
            (ATTR_QUALITY, self._quality),
            (ATTR_TIME, self._time),
        ):
            if value or isinstance(value, bool):
                attributes[key] = value
        return attributes
