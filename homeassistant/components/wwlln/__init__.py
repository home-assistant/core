"""Support for World Wide Lightning Location Network."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS,
    CONF_UNIT_SYSTEM_IMPERIAL, LENGTH_KILOMETERS, LENGTH_MILES)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import configured_instances
from .const import DATA_CLIENT, DEFAULT_RADIUS, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_RADIUS = 'radius'

DATA_LISTENER = 'listener'

DEFAULT_ATTRIBUTION = 'Data provided by the WWLLN'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

TOPIC_DATA_UPDATE = 'data_update'

UNIT_DYNAMIC = 'dynamic'
UNIT_STRIKES = 'strikes'

TYPE_NEAREST_STRIKE_DISTANCE = 'nearest_strike_distance'
TYPE_NUM_NEARBY_STRIKES = 'num_nearby_strikes'

SENSOR_TYPES = {
    TYPE_NEAREST_STRIKE_DISTANCE: (
        'Nearest Strike Distance', 'mdi:map-marker-distance', UNIT_DYNAMIC),
    TYPE_NUM_NEARBY_STRIKES: (
        'Number of Nearby Strikes', 'mdi:flash', UNIT_STRIKES)
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the WWLLN component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)

    identifier = '{0}, {1}'.format(latitude, longitude)
    if identifier in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': SOURCE_IMPORT},
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: conf[CONF_RADIUS]
            }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the WWLLN as config entry."""
    from aiowwlln import Client

    websession = aiohttp_client.async_get_clientsession(hass)

    wwlln = WWLLN(
        Client(websession),
        config_entry.data[CONF_LATITUDE],
        config_entry.data[CONF_LONGITUDE],
        config_entry.data[CONF_RADIUS],
        hass.config.units.name)

    await wwlln.async_update()

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = wwlln

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            config_entry, 'sensor'))

    async def refresh(event_time):
        """Refresh WWLLN sensor data."""
        _LOGGER.debug('Refreshing WWLLN data')
        await wwlln.async_update()
        async_dispatcher_send(hass, TOPIC_DATA_UPDATE)

    hass.data[DOMAIN][DATA_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass,
            refresh,
            DEFAULT_SCAN_INTERVAL)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an WWLLN config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
    cancel = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    cancel()

    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'sensor')

    return True


class WWLLN:
    """Define a class to handle WWLLN requests and data."""

    def __init__(self, client, latitude, longitude, radius, unit_system):
        """Initialize."""
        self._client = client
        self.latitude = latitude
        self.longitude = longitude
        self.nearby_strikes = []
        self.nearest_strike = {}
        self.radius = radius
        self.unit_system = unit_system

    async def async_update(self):
        """Update to latest data."""
        from aiowwlln.errors import WWLLNError

        tasks = {
            'nearby_strikes': self._client.within_radius(
                self.latitude,
                self.longitude,
                self.radius,
                unit=self.unit_system),
            'nearest_strike': self._client.nearest(
                self.latitude, self.longitude)
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for attr, result in zip(tasks, results):
            if isinstance(result, WWLLNError):
                _LOGGER.error(
                    'There was an error while updating "%s": %s', attr, result)
                continue
            setattr(self, attr, result)


class WWLLNEntity(Entity):
    """Define a base WWLLN entity."""

    def __init__(self, wwlln, sensor_type, name, icon, unit):
        """Initialize the sensor."""
        self._async_unsub_dispatcher_connect = None
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit
        self._wwlln = wwlln

        self._attrs = {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_RADIUS: self._wwlln.radius
        }

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon to use in the front-end."""
        return self._icon

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self):
        """Return a unique, unchanging string that represents this entity."""
        return '{0},{1}_{2}'.format(
            self._wwlln.latitude, self._wwlln.longitude, self._sensor_type)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._unit != UNIT_DYNAMIC:
            return self._unit

        if self._wwlln.unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_DATA_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
