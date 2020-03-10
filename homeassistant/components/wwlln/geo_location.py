"""Support for WWLLN geo location events."""
from datetime import timedelta
import logging

from aiowwlln.errors import WWLLNError

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_WINDOW, DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_EXTERNAL_ID = "external_id"
ATTR_PUBLICATION_DATE = "publication_date"

DEFAULT_ATTRIBUTION = "Data provided by the WWLLN"
DEFAULT_EVENT_NAME = "Lightning Strike: {0}"
DEFAULT_ICON = "mdi:flash"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=10)

SIGNAL_DELETE_ENTITY = "wwlln_delete_entity_{0}"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WWLLN based on a config entry."""
    client = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    manager = WWLLNEventManager(
        hass,
        async_add_entities,
        client,
        entry.data[CONF_LATITUDE],
        entry.data[CONF_LONGITUDE],
        entry.data[CONF_RADIUS],
        entry.data[CONF_WINDOW],
    )
    await manager.async_init()


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
        window_seconds,
    ):
        """Initialize."""
        self._async_add_entities = async_add_entities
        self._client = client
        self._hass = hass
        self._latitude = latitude
        self._longitude = longitude
        self._managed_strike_ids = set()
        self._radius = radius
        self._strikes = {}
        self._window = timedelta(seconds=window_seconds)

        if hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            self._unit = LENGTH_MILES
        else:
            self._unit = LENGTH_KILOMETERS

    @callback
    def _create_events(self, ids_to_create):
        """Create new geo location events."""
        _LOGGER.debug("Going to create %s", ids_to_create)
        events = []
        for strike_id in ids_to_create:
            strike = self._strikes[strike_id]
            event = WWLLNEvent(
                strike["distance"],
                strike["lat"],
                strike["long"],
                self._unit,
                strike_id,
                strike["unixTime"],
            )
            events.append(event)

        self._async_add_entities(events)

    @callback
    def _remove_events(self, ids_to_remove):
        """Remove old geo location events."""
        _LOGGER.debug("Going to remove %s", ids_to_remove)
        for strike_id in ids_to_remove:
            async_dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(strike_id))

    async def async_init(self):
        """Schedule regular updates based on configured time interval."""

        async def update(event_time):
            """Update."""
            await self.async_update()

        await self.async_update()
        async_track_time_interval(self._hass, update, DEFAULT_UPDATE_INTERVAL)

    async def async_update(self):
        """Refresh data."""
        _LOGGER.debug("Refreshing WWLLN data")

        try:
            self._strikes = await self._client.within_radius(
                self._latitude,
                self._longitude,
                self._radius,
                unit=self._hass.config.units.name,
                window=self._window,
            )
        except WWLLNError as err:
            _LOGGER.error("Error while updating WWLLN data: %s", err)
            return

        new_strike_ids = set(self._strikes)
        # Remove all managed entities that are not in the latest update anymore.
        ids_to_remove = self._managed_strike_ids.difference(new_strike_ids)
        self._remove_events(ids_to_remove)

        # Create new entities for all strikes that are not managed entities yet.
        ids_to_create = new_strike_ids.difference(self._managed_strike_ids)
        self._create_events(ids_to_create)

        # Store all external IDs of all managed strikes.
        self._managed_strike_ids = new_strike_ids


class WWLLNEvent(GeolocationEvent):
    """Define a lightning strike event."""

    def __init__(
        self, distance, latitude, longitude, unit, strike_id, publication_date
    ):
        """Initialize entity with data provided."""
        self._distance = distance
        self._latitude = latitude
        self._longitude = longitude
        self._publication_date = publication_date
        self._remove_signal_delete = None
        self._strike_id = strike_id
        self._unit_of_measurement = unit

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._strike_id),
            (ATTR_ATTRIBUTION, DEFAULT_ATTRIBUTION),
            (ATTR_PUBLICATION_DATE, utc_from_timestamp(self._publication_date)),
        ):
            attributes[key] = value
        return attributes

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
        return DEFAULT_EVENT_NAME.format(self._strike_id)

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return DOMAIN

    @property
    def should_poll(self):
        """Disable polling."""
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
            self.hass,
            SIGNAL_DELETE_ENTITY.format(self._strike_id),
            self._delete_callback,
        )
