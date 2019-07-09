"""Support for WWLLN geo location events."""
from datetime import timedelta
from itertools import filterfalse
import logging

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS, CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL, LENGTH_KILOMETERS, LENGTH_MILES)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.event import async_track_time_interval

from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_EVENT_NAME = 'Lightning Strike'
DEFAULT_ICON = 'mdi:flash'
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)

SIGNAL_DELETE_ENTITY = 'delete_entity_{0}'


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WWLLN sensors based on a config entry."""
    client = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    WWLLNEventManager(
        hass,
        async_add_entities,
        client,
        entry.data[CONF_LATITUDE],
        entry.data[CONF_LONGITUDE],
        entry.data[CONF_RADIUS],
        entry.data[CONF_UNIT_SYSTEM])


def get_new_strikes(old_strike_list, new_strike_list):
    """Return new strike data by comparing old and new lists."""
    old_iter = filterfalse(lambda x: x in old_strike_list, new_strike_list)
    new_iter = filterfalse(lambda x: x in new_strike_list, old_strike_list)
    return list(old_iter) + list(new_iter)


class WWLLNEventManager:
    """Define a class to handle WWLLN events."""

    def __init__(
            self,
            hass,
            async_add_entities,
            client,
            latitude,
            longitude,
            radius,
            unit_system):
        """Initialize."""
        self._async_add_entities = async_add_entities
        self._client = client
        self._hass = hass
        self._latitude = latitude
        self._longitude = longitude
        self._managed_strike_ids = set()
        self._radius = radius
        self._strikes = {}

        self._unit_system = unit_system
        if unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
            self._unit = LENGTH_MILES
        else:
            self._unit = LENGTH_KILOMETERS

        self._init_regular_updates()

    async def _init_regular_updates(self):
        """Schedule regular updates based on configured time interval."""
        async_track_time_interval(
            self._hass, self._refresh, DEFAULT_UPDATE_INTERVAL)

    @callback
    def _create_events(self, ids_to_create):
        """Create new geo location events."""
        events = []
        for strike_id in ids_to_create:
            strike = self._strikes[strike_id]
            event = WWLLNEvent(
                strike["distance"],
                strike["lat"],
                strike["long"],
                self._unit,
                strike_id)
            events.append(event)

        self._async_add_entities(events)

    @callback
    def _remove_events(self, ids_to_remove):
        """Remove old geo location events."""
        for strike_id in ids_to_remove:
            async_dispatcher_send(
                self._hass, SIGNAL_DELETE_ENTITY.format(strike_id))

    async def _refresh(self):
        """Refresh data."""
        from aiowwlln.errors import WWLLNError

        try:
            self._strikes = await self._client.within_radius(
                self._latitude,
                self._longitude,
                self._radius,
                unit=self._unit_system)
        except WWLLNError as err:
            _LOGGER.error('Error while updating WWLLN data: %s', err)
            return

        new_strike_ids = set(self._strikes)
        ids_to_remove = self._managed_strike_ids.difference(new_strike_ids)
        self._hass.async_create_task(self._remove_events(ids_to_remove))

        ids_to_create = new_strike_ids.difference(self._managed_strike_ids)
        self._hass.async_create_task(self._create_events(ids_to_create))


class WWLLNEvent(GeolocationEvent):
    """Define a lightning strike event."""

    def __init__(self, distance, latitude, longitude, unit, strike_id):
        """Initialize entity with data provided."""
        self._distance = distance
        self._latitude = latitude
        self._longitude = longitude
        self._remove_signal_delete = None
        self._strike_id = strike_id
        self._unit_of_measurement = unit

    @property
    def distance(self):
        """Return distance value of this external event."""
        return self._distance

    @property
    def icon(self):
        """Return the icon to use in the front-end."""
        return DEFAULT_ICON

    @property
    def latitude(self):
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self):
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def name(self):
        """Return the name of the event."""
        return DEFAULT_EVENT_NAME

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return DOMAIN

    @property
    def should_poll(self):
        """No polling needed for a demo geolocation event."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @callback
    def _delete_callback(self):
        """Remove this entity."""
        self._remove_signal_delete()
        self.hass.async_create_task(self.async_remove())

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass, SIGNAL_DELETE_ENTITY.format(self._strike_id),
            self._delete_callback)
