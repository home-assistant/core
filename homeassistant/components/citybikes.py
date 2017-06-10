"""
CityBikes component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/citybikes/
"""
import logging
from datetime import timedelta

import asyncio
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, EVENT_TIME_CHANGED,
    ATTR_ATTRIBUTION, ATTR_LOCATION, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_NOW)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import location, dt, slugify

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
                      " %s", err)
        return None


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Citybikes bike sharing system component."""
    networks = {}

    for location_config in config.get(DOMAIN):
        @asyncio.coroutine
        def async_setup_single_network(config):
            """Set up a single CityBikes network."""
            network_id = config.get(CONF_NETWORK)
            latitude = config.get(CONF_LATITUDE, hass.config.latitude)
            longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
            if not network_id:
                # Autodetect network from location
                network_id = yield from _get_closest_network_id(hass,
                                                                latitude,
                                                                longitude)
                if not network_id:
                    # Autodetection failed - try again later.
                    #
                    # Since this function must receive the `config` variable,
                    # we can't use the standard track_point_in_time helpers,
                    # as they pass the current time as the one and only
                    # argument. So this is a copy of the
                    # `async_track_point_in_utc_time` helper function, that
                    # passes `config` as the argument, instead.
                    later_time = dt.utcnow() + SCAN_INTERVAL

                    @callback
                    def listener(event):
                        """Listen for matching time_changed events."""
                        now = event.data[ATTR_NOW]

                        if now < later_time or hasattr(listener, 'run'):
                            return

                        # Set variable so that we will never run twice.
                        # Because the event bus might have to wait till a
                        # thread comes available to execute this listener it
                        # might occur that the listener gets lined up twice to
                        # be executed. This will make sure the second time it
                        # does nothing.
                        listener.run = True
                        async_unsub()

                        hass.async_run_job(async_setup_single_network, config)

                    async_unsub = hass.bus.async_listen(EVENT_TIME_CHANGED,
                                                        listener)
                    return

            if network_id not in networks:
                network = CityBikesNetwork(hass, network_id)
                yield from network.async_update(dt.utcnow())
                networks[network_id] = network

            if CONF_STATIONS_LIST in config:
                networks[network_id].start_monitoring_stations(
                    *config.get(CONF_STATIONS_LIST))
            else:
                radius = config.get(CONF_RADIUS)
                networks[network_id].start_monitoring_area(latitude, longitude,
                                                           radius)

        yield from async_setup_single_network(location_config)

    return True


class CityBikesNetwork:
    """Representation of a bike sharing network."""

    def __init__(self, hass, network_id):
        """Initialize the Network entity."""
        self.hass = hass
        self._network_id = network_id
        self._stations_data = []
        self._stations = {}
        self._monitored_areas = set()
        self._monitored_stations = set()
        async_track_time_interval(self.hass, self.async_update, SCAN_INTERVAL)

    @asyncio.coroutine
    def _fetch_stations(self):
        try:
            session = async_get_clientsession(self.hass)

            with async_timeout.timeout(5, loop=self.hass.loop):
                req = yield from session.get(DEFAULT_ENDPOINT.format(
                    uri=STATIONS_URI.format(uid=self._network_id)))

            json_response = yield from req.json()
            network = STATIONS_RESPONSE_SCHEMA(json_response)
            self._stations_data = network[ATTR_NETWORK][ATTR_STATIONS_LIST]

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Could not connect to CityBikes API endpoint")
        except ValueError:
            _LOGGER.error("Received non-JSON data from CityBikes API"
                          " endpoint")
        except vol.Invalid as err:
            _LOGGER.error("Received unexpected JSON from CityBikes API"
                          " endpoint: %s", err)

    @asyncio.coroutine
    def async_update(self, now):
        """Update the bike sharing network.

        The state of the network is updated, followed by an update of all the
        associated station entities.
        """
        yield from self._fetch_stations()
        for station in self._stations_data:
            for latitude, longitude, radius in self._monitored_areas:
                dist = location.distance(latitude, longitude,
                                         station.get(ATTR_LATITUDE),
                                         station.get(ATTR_LONGITUDE))
                if dist < radius:
                    self._add_station_entity(station)

            station_id = station[ATTR_ID]

            if station_id in self._monitored_stations or \
                    ATTR_EXTRA in station and \
                    ATTR_UID in station[ATTR_EXTRA] and \
                    station[ATTR_EXTRA][ATTR_UID] in self._monitored_stations:
                self._add_station_entity(station)

            if station_id in self._stations:
                yield from self._stations[station_id].async_update_data(
                    station)

    def _add_station_entity(self, station):
        entity_id = CityBikesStation.make_entity_id(self._network_id,
                                                    station[ATTR_ID])
        if not self.hass.states.get(entity_id):
            self._stations[station[ATTR_ID]] = CityBikesStation(
                self.hass, self._network_id, station)

    def start_monitoring_area(self, latitude, longitude, radius):
        """Start monitoring stations in an area."""
        self._monitored_areas.update([(latitude, longitude, radius)])
        self.hass.async_add_job(self.async_update(dt.utcnow()))

    def start_monitoring_stations(self, *stations):
        """Start monitoring specific stations."""
        self._monitored_stations.update(stations)
        self.hass.async_add_job(self.async_update(dt.utcnow()))


class CityBikesStation(Entity):
    """Representation of a bike sharing station."""

    @staticmethod
    def make_entity_id(network_id, station_id):
        """Generate an entity ID."""
        return "{}.{}_{}".format(DOMAIN, slugify(network_id), station_id)

    def __init__(self, hass, network_id, station_data):
        """Initialize the Station entity."""
        self.hass = hass
        self._network_id = network_id
        self._station_data = station_data

    @property
    def should_poll(self):
        """Indicate whether HASS should poll the station for state updates."""
        return False

    @property
    def name(self):
        """Return the name of the station."""
        return self._station_data[ATTR_NAME]

    @property
    def entity_id(self):
        """Return the entity ID of the station."""
        return CityBikesStation.make_entity_id(
            self._network_id, self._station_data[ATTR_ID])

    @property
    def state(self):
        """Return the state of the station."""
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
        """Update the internal data state of the station."""
        self._station_data = station_data
        yield from self.async_update_ha_state()
