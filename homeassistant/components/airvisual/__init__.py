"""
Support for AirVisual air quality data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/airvisual/
"""
from logging import getLogger
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL, CONF_STATE, CONF_SHOW_ON_MAP)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import configured_instances, identifier_from_config
from .const import (
    CONF_CITY, CONF_COORDINATES, CONF_COUNTRY, CONF_LOCATION, DATA_CLIENT,
    DATA_LISTENER, DEFAULT_SCAN_INTERVAL, DOMAIN, TOPIC_UPDATE)

REQUIREMENTS = ['pyairvisual==2.0.1']
_LOGGER = getLogger(__name__)

SENSOR_LOCALES = {'cn': 'Chinese', 'us': 'U.S.'}

LOCATION_COORDINATE_SCHEMA = vol.Schema({
    vol.Required(CONF_LATITUDE): cv.latitude,
    vol.Required(CONF_LONGITUDE): cv.longitude,
})

LOCATION_NAME_SCHEMA = vol.Schema({
    vol.Required(CONF_CITY): cv.string,
    vol.Required(CONF_COUNTRY): cv.string,
    vol.Required(CONF_STATE): cv.string,
})

API_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY):
        cv.string,
    vol.Exclusive(CONF_COORDINATES, 'location'):
        LOCATION_COORDINATE_SCHEMA,
    vol.Exclusive(CONF_LOCATION, 'location'):
        LOCATION_NAME_SCHEMA,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_LOCALES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_LOCALES)]),
    vol.Optional(CONF_SHOW_ON_MAP, default=True):
        cv.boolean,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        cv.time_period
})

# Using this slightly strange schema in anticipation of some forthcoming
# functionality that will expand it:
CONFIG_SCHEMA = vol.Schema({DOMAIN: API_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the AirVisual component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    identifier = identifier_from_config(hass, conf)
    if identifier in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={'source': SOURCE_IMPORT}, data=conf))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up AirVisual as config entry."""
    from pyairvisual import Client
    from pyairvisual.errors import AirVisualError

    city = config_entry.data.get(CONF_LOCATION, {}).get(CONF_CITY)
    state = config_entry.data.get(CONF_LOCATION, {}).get(CONF_STATE)
    country = config_entry.data.get(CONF_LOCATION, {}).get(CONF_COUNTRY)

    latitude = config_entry.data.get(CONF_COORDINATES, {}).get(
        CONF_LATITUDE, hass.config.latitude)
    longitude = config_entry.data.get(CONF_COORDINATES, {}).get(
        CONF_LONGITUDE, hass.config.longitude)

    websession = aiohttp_client.async_get_clientsession(hass)

    if city:
        _LOGGER.debug(
            'Using location by name: %s, %s, %s', city, state, country)
        airvisual = AirVisual(
            Client(config_entry.data[CONF_API_KEY], websession),
            config_entry.data.get(
                CONF_MONITORED_CONDITIONS, list(SENSOR_LOCALES)),
            city=city,
            state=state,
            country=country,
            show_on_map=config_entry.data.get(CONF_SHOW_ON_MAP, True))
    else:
        _LOGGER.debug(
            'Using location by coordinates: %s, %s', latitude, longitude)
        airvisual = AirVisual(
            Client(config_entry.data[CONF_API_KEY], websession),
            config_entry.data.get(
                CONF_MONITORED_CONDITIONS, list(SENSOR_LOCALES)),
            latitude=latitude,
            longitude=longitude,
            show_on_map=config_entry.data.get(CONF_SHOW_ON_MAP, True))

    try:
        await airvisual.async_update()
    except AirVisualError as err:
        _LOGGER.error('Config entry failed: %s', err)
        raise ConfigEntryNotReady

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = airvisual

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, 'sensor'))

    async def update_data(service):
        """Refresh OpenUV data."""
        _LOGGER.debug('Refreshing AirVisual data')
        await airvisual.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DOMAIN][DATA_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass, update_data,
            timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL]))

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an AirVisual config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(
        config_entry.entry_id)
    remove_listener()

    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'sensor')

    return True


class AirVisual:
    """Define a generic AirVisual data object."""

    def __init__(self, client, monitored_conditions, **kwargs):
        """Initialize."""
        self._client = client
        self.city = kwargs.get(CONF_CITY)
        self.country = kwargs.get(CONF_COUNTRY)
        self.latitude = kwargs.get(CONF_LATITUDE)
        self.longitude = kwargs.get(CONF_LONGITUDE)
        self.monitored_conditions = monitored_conditions
        self.pollution_info = {}
        self.show_on_map = kwargs[CONF_SHOW_ON_MAP]
        self.state = kwargs.get(CONF_STATE)

        if self.city:
            self.identifier = '{0}, {1}, {2}'.format(
                self.city, self.state, self.country)
        else:
            self.identifier = '{0}, {1}'.format(self.latitude, self.longitude)

    async def async_update(self):
        """Update sensor data."""
        from pyairvisual.errors import AirVisualError

        try:
            if self.city:
                resp = await self._client.data.city(
                    self.city, self.state, self.country)
                self.longitude, self.latitude = resp['location']['coordinates']
            else:
                resp = await self._client.data.nearest_city(
                    self.latitude, self.longitude)

            _LOGGER.debug("New data retrieved: %s", resp)

            self.pollution_info = resp['current']['pollution']
        except (KeyError, AirVisualError) as err:
            if self.city:
                location = (self.city, self.state, self.country)
            else:
                location = (self.latitude, self.longitude)

            _LOGGER.error(
                "Can't retrieve data for location: %s (%s)", location, err)

            self.pollution_info = {}
