"""
CityBikes component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/citybikes/
"""
import logging
import voluptuous as vol
from datetime import timedelta

import asyncio
import aiohttp
import async_timeout

from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE,
    ATTR_ATTRIBUTION, ATTR_LOCATION, ATTR_LATITUDE, ATTR_LONGITUDE)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import event
from homeassistant.util import location, slugify, dt
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_ENDPOINT = 'https://api.citybik.es/{uri}'
NETWORKS_URI = 'v2/networks'
STATIONS_URI = 'v2/networks/{uid}?fields=network.stations'

SCAN_INTERVAL = timedelta(seconds=15)  # Timely, and doesn't suffocate the API
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

LOCATION_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RADIUS, CONF_STATIONS_LIST),
    vol.Schema({
        vol.Optional(CONF_NAME, default=""): cv.string,
        vol.Optional(CONF_NETWORK, default=""): cv.string,
        vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude,
        vol.Exclusive(CONF_RADIUS, 'station_filter'):
            cv.positive_int,
        vol.Exclusive(CONF_STATIONS_LIST, 'station_filter'):
            vol.All(
                cv.ensure_list,
                vol.Length(min=1),
                [cv.string])
    }))

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [LOCATION_SCHEMA])
}, extra=vol.ALLOW_EXTRA)

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


@asyncio.coroutine
def _get_closest_network_id(hass, latitude, longitude):
    try:
        dist = -1
        session = async_get_clientsession(hass)
        with async_timeout.timeout(5, loop=hass.loop):
            req = yield from session.get(DEFAULT_ENDPOINT.format(
                uri=NETWORKS_URI))
        res = yield from req.json()
        res = NETWORKS_RESPONSE_SCHEMA(res)
        network = res[ATTR_NETWORKS_LIST][0]
        result = network[ATTR_ID]
        minimum_dist = location.distance(
            latitude, longitude,
            network[ATTR_LOCATION][ATTR_LATITUDE],
            network[ATTR_LOCATION][ATTR_LONGITUDE])
        for network in res[ATTR_NETWORKS_LIST][1:]:
            dist = location.distance(latitude, longitude,
                                     network[ATTR_LOCATION][ATTR_LATITUDE],
                                     network[ATTR_LOCATION][ATTR_LONGITUDE])
            if dist < minimum_dist:
                minimum_dist = dist
                result = network[ATTR_ID]

        return result
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Could not connect to CityBikes API endpoint")
        return None
    except ValueError:
        _LOGGER.error("Received non-JSON data from CityBikes API endpoint")
        return None
    except vol.Invalid as err:
        _LOGGER.error("Received unexpected JSON from CityBikes API endpoint: "
                      " {}".format(err))
        return None


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Citybikes bike sharing system component."""
    networks = {}

    for location_config in config.get(DOMAIN):
        @asyncio.coroutine
        def async_setup_single_network(now):
            """Set up a single CityBikes network."""
            network_id = location_config.get(CONF_NETWORK)

            latitude = location_config.get(CONF_LATITUDE,
                                           hass.config.latitude)
            longitude = location_config.get(CONF_LONGITUDE,
                                            hass.config.longitude)

            if not network_id:
                # Autodetect network from location
                network_id = yield from _get_closest_network_id(hass, latitude,
                                                                longitude)

                if not network_id:
                    # Autodetection failed - try again later
                    one_minute_later = dt.utcnow() + timedelta(minutes=1)
                    event.async_track_point_in_utc_time(
                        hass, async_setup_single_network, one_minute_later)
                    return

            if network_id not in networks:
                network = CityBikesNetwork(hass, network_id)

                @asyncio.coroutine
                def async_update_single_network(now):
                    yield from network.async_update_ha_state(True)
                    event.async_track_point_in_utc_time(
                        hass, async_update_single_network,
                        dt.utcnow() + SCAN_INTERVAL)

                yield from async_update_single_network(None)
                networks[network_id] = network

            if CONF_STATIONS_LIST in location_config:
                networks[network_id].start_monitoring_stations(
                    *location_config.get(CONF_STATIONS_LIST))
            else:
                radius = location_config.get(CONF_RADIUS)
                networks[network_id].start_monitoring_area(latitude, longitude,
                                                           radius)

        yield from async_setup_single_network(None)

    return True


class CityBikesNetwork(Entity):
    """Representation of a bike sharing network."""

    def __init__(self, hass, network_id):
        """Initialize the Network entity."""
        self.hass = hass
        self._network_id = network_id
        self._stations_data = []
        self._stations = {}
        self._monitored_areas = set()
        self._monitored_stations = set()

    @property
    def name(self):
        return self._network_id

    @property
    def entity_id(self):
        return "{}.{}".format(DOMAIN, slugify(self.name))

    @asyncio.coroutine
    def _fetch_stations(self):
        try:
            session = async_get_clientsession(self.hass)
            with async_timeout.timeout(5, loop=self.hass.loop):
                req = yield from session.get(DEFAULT_ENDPOINT.format(
                    uri=STATIONS_URI.format(uid=self._network_id)))
            response = yield from req.json()
            response = STATIONS_RESPONSE_SCHEMA(response)
            self._stations_data = response[ATTR_NETWORK][ATTR_STATIONS_LIST]
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Could not connect to CityBikes API endpoint")
        except ValueError:
            _LOGGER.error("Received non-JSON data from CityBikes API"
                          " endpoint")
        except vol.Invalid as err:
            _LOGGER.error("Received unexpected JSON from CityBikes API"
                          " endpoint: {}".format(err))

    @asyncio.coroutine
    def async_update(self):
        yield from self._fetch_stations()
        for station in self._stations_data:
            for latitude, longitude, radius in self._monitored_areas:
                dist = location.distance(latitude, longitude,
                                         station.get(ATTR_LATITUDE),
                                         station.get(ATTR_LONGITUDE))
                if dist < radius:
                    self._add_station_entity_if_necessary(station)

            station_id = station[ATTR_ID]

            if station_id in self._monitored_stations or \
                ATTR_EXTRA in station and ATTR_UID in station[ATTR_EXTRA] and \
                station[ATTR_EXTRA][ATTR_UID] in self._monitored_stations:
                self._add_station_entity_if_necessary(station)

            if station_id in self._stations:
                yield from self._stations[station_id].async_update_data(station)

    def _add_station_entity_if_necessary(self, station):
        entity_id = CityBikesStation.make_entity_id(self.entity_id,
                                                    station[ATTR_ID])
        if not self.hass.states.get(entity_id):
            self._stations[station[ATTR_ID]] = CityBikesStation(
                self.hass, self._network_id, station)

    def start_monitoring_area(self, latitude, longitude, radius):
        """Start monitoring stations in an area."""
        self._monitored_areas.update([(latitude, longitude, radius)])

    def start_monitoring_stations(self, *stations):
        """Start monitoring specific stations."""
        self._monitored_stations.update(stations)


class CityBikesStation(Entity):
    """Representation of a bike sharing station."""

    @staticmethod
    def make_entity_id(network_id, station_id):
        return "{}.{}_{}".format(DOMAIN, network_id, station_id)

    def __init__(self, hass, network_id, station_data):
        """Initialize the Station entity."""
        self.hass = hass
        self._network_id = network_id
        self._station_data = station_data

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._station_data[ATTR_NAME]

    @property
    def entity_id(self):
        return CityBikesStation.make_entity_id(
            self._network_id, self._station_data[ATTR_ID])

    @property
    def state(self):
        return self._station_data.get(ATTR_FREE_BIKES)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return dict(
            {ATTR_ATTRIBUTION: CITYBIKES_ATTRIBUTION}, **self._station_data)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'bikes'

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:bike'

    @asyncio.coroutine
    def async_update_data(self, station_data):
        self._station_data = station_data
        yield from self.async_update_ha_state()
