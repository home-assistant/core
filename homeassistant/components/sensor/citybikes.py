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

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS,
    ATTR_ATTRIBUTION, ATTR_LOCATION, ATTR_LATITUDE, ATTR_LONGITUDE,
    STATE_UNKNOWN, LENGTH_METERS, LENGTH_FEET, ATTR_ID)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import location, distance

_LOGGER = logging.getLogger(__name__)

ATTR_EMPTY_SLOTS = 'empty_slots'
ATTR_EXTRA = 'extra'
ATTR_FREE_BIKES = 'free_bikes'
ATTR_NAME = 'name'
ATTR_NETWORK = 'network'
ATTR_NETWORKS_LIST = 'networks'
ATTR_STATIONS_LIST = 'stations'
ATTR_TIMESTAMP = 'timestamp'
ATTR_UID = 'uid'

CONF_NETWORK = 'network'
CONF_STATIONS_LIST = 'stations'

DEFAULT_ENDPOINT = 'https://api.citybik.es/{uri}'
PLATFORM = 'citybikes'

MONITORED_NETWORKS = 'monitored-networks'

NETWORKS_URI = 'v2/networks'

REQUEST_TIMEOUT = 5  # In seconds; argument to asyncio.timeout

SCAN_INTERVAL = timedelta(minutes=5)  # Timely, and doesn't suffocate the API

STATIONS_URI = 'v2/networks/{uid}?fields=network.stations'

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
            vol.All(cv.ensure_list, vol.Length(min=1), [cv.string])
    }))

NETWORK_SCHEMA = vol.Schema({
    vol.Required(ATTR_ID): cv.string,
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_LOCATION): vol.Schema({
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
        }, extra=vol.REMOVE_EXTRA),
    }, extra=vol.REMOVE_EXTRA)

NETWORKS_RESPONSE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NETWORKS_LIST): [NETWORK_SCHEMA],
    })

STATION_SCHEMA = vol.Schema({
    vol.Required(ATTR_FREE_BIKES): cv.positive_int,
    vol.Required(ATTR_EMPTY_SLOTS): vol.Any(cv.positive_int, None),
    vol.Required(ATTR_LATITUDE): cv.latitude,
    vol.Required(ATTR_LONGITUDE): cv.longitude,
    vol.Required(ATTR_ID): cv.string,
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_TIMESTAMP): cv.string,
    vol.Optional(ATTR_EXTRA):
        vol.Schema({vol.Optional(ATTR_UID): cv.string}, extra=vol.REMOVE_EXTRA)
    }, extra=vol.REMOVE_EXTRA)

STATIONS_RESPONSE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NETWORK): vol.Schema({
        vol.Required(ATTR_STATIONS_LIST): [STATION_SCHEMA]
        }, extra=vol.REMOVE_EXTRA)
    })


class CityBikesRequestError(Exception):
    """Error to indicate a CityBikes API request has failed."""

    pass


@asyncio.coroutine
def async_citybikes_request(hass, uri, schema):
    """Perform a request to CityBikes API endpoint, and parse the response."""
    try:
        session = async_get_clientsession(hass)

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            req = yield from session.get(DEFAULT_ENDPOINT.format(uri=uri))

        json_response = yield from req.json()
        return schema(json_response)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Could not connect to CityBikes API endpoint")
    except ValueError:
        _LOGGER.error("Received non-JSON data from CityBikes API endpoint")
    except vol.Invalid as err:
        _LOGGER.error("Received unexpected JSON from CityBikes"
                      " API endpoint: %s", err)
    raise CityBikesRequestError


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):
    """Set up the CityBikes platform."""
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {MONITORED_NETWORKS: {}}

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

    if network_id not in hass.data[PLATFORM][MONITORED_NETWORKS]:
        network = CityBikesNetwork(hass, network_id)
        hass.data[PLATFORM][MONITORED_NETWORKS][network_id] = network
        hass.async_add_job(network.async_refresh)
        async_track_time_interval(hass, network.async_refresh,
                                  SCAN_INTERVAL)
    else:
        network = hass.data[PLATFORM][MONITORED_NETWORKS][network_id]

    yield from network.ready.wait()

    devices = []
    for station in network.stations:
        dist = location.distance(latitude, longitude,
                                 station[ATTR_LATITUDE],
                                 station[ATTR_LONGITUDE])
        station_id = station[ATTR_ID]
        station_uid = str(station.get(ATTR_EXTRA, {}).get(ATTR_UID, ''))

        if radius > dist or stations_list.intersection((station_id,
                                                        station_uid)):
            devices.append(CityBikesStation(hass, network, station_id, name))

    async_add_devices(devices, True)


class CityBikesNetwork:
    """Thin wrapper around a CityBikes network object."""

    NETWORKS_LIST = None
    NETWORKS_LIST_LOADING = asyncio.Condition()

    @classmethod
    @asyncio.coroutine
    def get_closest_network_id(cls, hass, latitude, longitude):
        """Return the id of the network closest to provided location."""
        try:
            yield from cls.NETWORKS_LIST_LOADING.acquire()
            if cls.NETWORKS_LIST is None:
                networks = yield from async_citybikes_request(
                    hass, NETWORKS_URI, NETWORKS_RESPONSE_SCHEMA)
                cls.NETWORKS_LIST = networks[ATTR_NETWORKS_LIST]
            networks_list = cls.NETWORKS_LIST
            network = networks_list[0]
            result = network[ATTR_ID]
            minimum_dist = location.distance(
                latitude, longitude,
                network[ATTR_LOCATION][ATTR_LATITUDE],
                network[ATTR_LOCATION][ATTR_LONGITUDE])
            for network in networks_list[1:]:
                network_latitude = network[ATTR_LOCATION][ATTR_LATITUDE]
                network_longitude = network[ATTR_LOCATION][ATTR_LONGITUDE]
                dist = location.distance(latitude, longitude,
                                         network_latitude, network_longitude)
                if dist < minimum_dist:
                    minimum_dist = dist
                    result = network[ATTR_ID]

            return result
        except CityBikesRequestError:
            raise PlatformNotReady
        finally:
            cls.NETWORKS_LIST_LOADING.release()

    def __init__(self, hass, network_id):
        """Initialize the network object."""
        self.hass = hass
        self.network_id = network_id
        self.stations = []
        self.ready = asyncio.Event()

    @asyncio.coroutine
    def async_refresh(self, now=None):
        """Refresh the state of the network."""
        try:
            network = yield from async_citybikes_request(
                self.hass, STATIONS_URI.format(uid=self.network_id),
                STATIONS_RESPONSE_SCHEMA)
            self.stations = network[ATTR_NETWORK][ATTR_STATIONS_LIST]
            self.ready.set()
        except CityBikesRequestError:
            if now is not None:
                self.ready.clear()
            else:
                raise PlatformNotReady


class CityBikesStation(Entity):
    """CityBikes API Sensor."""

    def __init__(self, hass, network, station_id, base_name=''):
        """Initialize the sensor."""
        self._network = network
        self._station_id = station_id
        self._station_data = {}
        if base_name:
            uid = "_".join([network.network_id, base_name, station_id])
        else:
            uid = "_".join([network.network_id, station_id])
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, uid,
                                                  hass=hass)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._station_data.get(ATTR_FREE_BIKES, STATE_UNKNOWN)

    @property
    def name(self):
        """Return the name of the sensor."""
        if ATTR_NAME in self._station_data:
            return self._station_data[ATTR_NAME]
        return None

    @asyncio.coroutine
    def async_update(self):
        """Update station state."""
        if self._network.ready.is_set():
            for station in self._network.stations:
                if station[ATTR_ID] == self._station_id:
                    self._station_data = station
                    break

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._station_data:
            return {
                ATTR_ATTRIBUTION: CITYBIKES_ATTRIBUTION,
                ATTR_UID: self._station_data.get(ATTR_EXTRA, {}).get(ATTR_UID),
                ATTR_LATITUDE: self._station_data[ATTR_LATITUDE],
                ATTR_LONGITUDE: self._station_data[ATTR_LONGITUDE],
                ATTR_EMPTY_SLOTS: self._station_data[ATTR_EMPTY_SLOTS],
                ATTR_TIMESTAMP: self._station_data[ATTR_TIMESTAMP],
            }
        return {ATTR_ATTRIBUTION: CITYBIKES_ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'bikes'

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:bike'
