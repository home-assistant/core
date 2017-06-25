"""
Sensor for the CityBikes data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.citybikes/
"""
import logging
from datetime import timedelta

import asyncio
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE,
    ATTR_ATTRIBUTION, ATTR_LOCATION, ATTR_LATITUDE, ATTR_LONGITUDE,
    ATTR_FRIENDLY_NAME, STATE_UNKNOWN, LENGTH_METERS, LENGTH_FEET)
from homeassistant.helpers.event import (
    async_track_time_interval, async_track_point_in_utc_time)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import location, distance, dt as dt_util
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_ENDPOINT = 'https://api.citybik.es/{uri}'
NETWORKS_URI = 'v2/networks'
STATIONS_URI = 'v2/networks/{uid}?fields=network.stations'

SCAN_INTERVAL = timedelta(minutes=5)  # Timely, and doesn't suffocate the API
DOMAIN = 'citybikes'
CONF_NETWORK = 'network'
CONF_RADIUS = 'radius'
CONF_STATIONS_LIST = 'stations'
ATTR_NETWORKS_LIST = 'networks'
ATTR_NETWORK = 'network'
ATTR_STATIONS_LIST = 'stations'
ATTR_ID = 'id'
ATTR_UID = 'uid'
ATTR_NAME = 'name'
ATTR_EXTRA = 'extra'
ATTR_TIMESTAMP = 'timestamp'
ATTR_EMPTY_SLOTS = 'empty_slots'
ATTR_FREE_BIKES = 'free_bikes'
ATTR_TIMESTAMP = 'timestamp'
CITYBIKES_ATTRIBUTION = "Information provided by the CityBikes Project "\
                        "(https://citybik.es/#about)"


PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RADIUS, CONF_STATIONS_LIST),
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_NAME, default=''): cv.string,
        vol.Optional(CONF_NETWORK): cv.string,
        vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude,
        vol.Optional(CONF_RADIUS, 'station_filter'): cv.positive_int,
        vol.Optional(CONF_STATIONS_LIST, 'station_filter'):
            vol.All(
                cv.ensure_list,
                vol.Length(min=1),
                [cv.string])
    }))

NETWORK_SCHEMA = vol.Schema({
    vol.Required(ATTR_ID): cv.string,
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_LOCATION): vol.Schema({
        vol.Required(ATTR_LATITUDE): vol.Coerce(float),
        vol.Required(ATTR_LONGITUDE): vol.Coerce(float),
        }, extra=vol.REMOVE_EXTRA),
    }, extra=vol.REMOVE_EXTRA)

NETWORKS_RESPONSE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NETWORKS_LIST): [NETWORK_SCHEMA],
    })

STATION_SCHEMA = vol.Schema({
    vol.Required(ATTR_FREE_BIKES): cv.positive_int,
    vol.Required(ATTR_EMPTY_SLOTS): cv.positive_int,
    vol.Required(ATTR_LATITUDE): vol.Coerce(float),
    vol.Required(ATTR_LONGITUDE): vol.Coerce(float),
    vol.Required(ATTR_ID): cv.string,
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_TIMESTAMP): cv.string,
    vol.Optional(ATTR_EXTRA): vol.Schema({
        vol.Optional(ATTR_UID): cv.string
        }, extra=vol.REMOVE_EXTRA)
    }, extra=vol.REMOVE_EXTRA)

STATIONS_RESPONSE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NETWORK): vol.Schema({
        vol.Required(ATTR_STATIONS_LIST): [STATION_SCHEMA]
        }, extra=vol.REMOVE_EXTRA)
    })


MONITORED_NETWORKS = {}


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the CityBikes platform."""
    @asyncio.coroutine
    def async_setup_network(now=None):
        """Set up a network with stations without blocking."""
        latitude = config.get(CONF_LATITUDE, hass.config.latitude)
        longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
        network_id = config.get(CONF_NETWORK)
        stations_list = set(config.get(CONF_STATIONS_LIST, []))
        radius = config.get(CONF_RADIUS, 0)
        name = config.get(CONF_NAME)
        if not hass.config.units.is_metric:
            radius = distance.convert(radius, LENGTH_FEET, LENGTH_METERS)

        if not network_id:
            network_id = yield from CityBikesNetwork.get_closest_network_id(
                hass, latitude, longitude)
            if not network_id:
                async_track_point_in_utc_time(hass, async_setup_network,
                                              dt_util.utcnow() + SCAN_INTERVAL)
                return

        if network_id not in MONITORED_NETWORKS:
            network = CityBikesNetwork(hass, network_id)
            MONITORED_NETWORKS[network_id] = network
            hass.async_add_job(network.async_refresh)
            async_track_time_interval(hass, network.async_refresh,
                                      SCAN_INTERVAL)
        else:
            network = MONITORED_NETWORKS[network_id]

        while not network.ready:
            yield from asyncio.sleep(0.5)

        entities = []
        for station in network.stations:
            dist = location.distance(latitude, longitude,
                                     station[ATTR_LATITUDE],
                                     station[ATTR_LONGITUDE])
            station_id = station[ATTR_ID]
            station_uid = str(station.get(ATTR_EXTRA, {}).get(ATTR_UID, ''))

            if radius > dist or stations_list.intersection((station_id,
                                                            station_uid)):
                entities.append(CityBikesStation(network, station_id, name))

        async_add_entities(entities, True)

    hass.async_add_job(async_setup_network)


class CityBikesNetwork:
    """Thin wrapper around a CityBikes network object."""

    @classmethod
    @asyncio.coroutine
    def get_closest_network_id(cls, hass, latitude, longitude):
        """Return the id of the network closest to provided location."""
        try:
            session = async_get_clientsession(hass)
            with async_timeout.timeout(5, loop=hass.loop):
                req = yield from session.get(DEFAULT_ENDPOINT.format(
                    uri=NETWORKS_URI))
            json_response = yield from req.json()
            networks = NETWORKS_RESPONSE_SCHEMA(json_response)
            network = networks[ATTR_NETWORKS_LIST][0]
            result = network[ATTR_ID]
            minimum_dist = location.distance(
                latitude, longitude,
                network[ATTR_LOCATION][ATTR_LATITUDE],
                network[ATTR_LOCATION][ATTR_LONGITUDE])
            for network in networks[ATTR_NETWORKS_LIST][1:]:
                network_latitude = network[ATTR_LOCATION][ATTR_LATITUDE]
                network_longitude = network[ATTR_LOCATION][ATTR_LONGITUDE]
                dist = location.distance(latitude, longitude,
                                         network_latitude, network_longitude)
                if dist < minimum_dist:
                    minimum_dist = dist
                    result = network[ATTR_ID]

            return result
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Could not connect to CityBikes API endpoint")
            return None
        except ValueError:
            _LOGGER.error("Received non-JSON data from CityBikes"
                          " API endpoint")
            return None
        except vol.Invalid as err:
            _LOGGER.error("Received unexpected JSON from CityBikes"
                          " API endpoint: %s", err)
            return None

    def __init__(self, hass, network_id):
        """Initialize the network object."""
        self._hass = hass
        self._network_id = network_id
        self._stations = []
        self._ready = False

    @property
    def uid(self):
        """Return the network ID."""
        return self._network_id

    @property
    def stations(self):
        """Return the stations of the network."""
        return self._stations

    @property
    def ready(self):
        """Return the readiness state of the network object."""
        return self._ready

    @asyncio.coroutine
    def async_refresh(self, now=None):
        """Refresh the state of the network."""
        try:
            session = async_get_clientsession(self._hass)

            with async_timeout.timeout(5, loop=self._hass.loop):
                req = yield from session.get(DEFAULT_ENDPOINT.format(
                    uri=STATIONS_URI.format(uid=self._network_id)))

            json_response = yield from req.json()
            network = STATIONS_RESPONSE_SCHEMA(json_response)
            self._stations = network[ATTR_NETWORK][ATTR_STATIONS_LIST]
            self._ready = True
            return

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Could not connect to CityBikes API endpoint")
        except ValueError:
            _LOGGER.error("Received non-JSON data from CityBikes API"
                          " endpoint")
        except vol.Invalid as err:
            _LOGGER.error("Received unexpected JSON from CityBikes API"
                          " endpoint: %s", err)

        self._ready = False


class CityBikesStation(Entity):
    """CityBikes API Sensor."""

    def __init__(self, network, station_id, base_name=''):
        """Initialize the sensor."""
        self._network = network
        self._station_id = station_id
        self._station_data = {}
        self._base_name = base_name

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            return self._station_data[ATTR_FREE_BIKES]
        except KeyError:
            return STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._base_name:
            return "{} {} {}".format(self._network.uid, self._base_name,
                                     self._station_id)
        else:
            return "{} {}".format(self._network.uid, self._station_id)

    @asyncio.coroutine
    def async_update(self):
        """Update station state."""
        if self._network.ready:
            for station in self._network.stations:
                if station[ATTR_ID] == self._station_id:
                    self._station_data = station
                    break

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        try:
            return {
                ATTR_ATTRIBUTION: CITYBIKES_ATTRIBUTION,
                ATTR_UID: self._station_data.get(ATTR_EXTRA, {}).get(ATTR_UID),
                ATTR_LATITUDE: self._station_data[ATTR_LATITUDE],
                ATTR_LONGITUDE: self._station_data[ATTR_LONGITUDE],
                ATTR_EMPTY_SLOTS: self._station_data[ATTR_EMPTY_SLOTS],
                ATTR_FRIENDLY_NAME: self._station_data[ATTR_NAME],
                ATTR_TIMESTAMP: self._station_data[ATTR_TIMESTAMP],
            }
        except KeyError:
            return {ATTR_ATTRIBUTION: CITYBIKES_ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'bikes'

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:bike'
