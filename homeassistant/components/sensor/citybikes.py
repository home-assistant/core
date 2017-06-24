"""
Sensor for the CityBikes data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.citybikes/
"""
import logging
import asyncio
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE,
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_FRIENDLY_NAME,
    STATE_UNKNOWN, LENGTH_METERS, LENGTH_FEET)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, location, distance
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/aronsky/python-citybikes'
                '/archive/eb4a2dc25c7ef19812cef5a6163897465ae496b9.zip'
                '#python-citybikes==0.1.3-async']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)  # Timely, and doesn't suffocate the API
DOMAIN = 'citybikes'
CONF_NETWORK = 'network'
CONF_RADIUS = 'radius'
CONF_STATIONS_LIST = 'stations'
ATTR_ID = 'id'
ATTR_UID = 'uid'
ATTR_STATION_NAME = 'name'
ATTR_EXTRA = 'extra'
ATTR_EMPTY_SLOTS = 'empty_slots'
ATTR_FREE_BIKES = 'free_bikes'
ATTR_TIMESTAMP = 'timestamp'
CITYBIKES_ATTRIBUTION = "Information provided by the CityBikes Project "\
                        "(https://citybik.es/#about)"


PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RADIUS, CONF_STATIONS_LIST),
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_NETWORK): cv.string,
        vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude,
        vol.Exclusive(CONF_RADIUS, 'station_filter'): cv.positive_int,
        vol.Exclusive(CONF_STATIONS_LIST, 'station_filter'):
            vol.All(
                cv.ensure_list,
                vol.Length(min=1),
                [cv.string])
    }))


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the CityBikes platform."""
    from citybikes import Client, Network

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    network_id = config.get(CONF_NETWORK)
    stations_list = config.get(CONF_STATIONS_LIST, [])
    radius = config.get(CONF_RADIUS, 0)
    if not hass.config.units.is_metric:
        radius = distance.convert(radius, LENGTH_FEET, LENGTH_METERS)

    @asyncio.coroutine
    def async_setup_network():
        if not network_id:
            client = Client(loop=hass.loop)
            yield from client.networks.async_request()
            network = client.networks.near(latitude, longitude)[0][0]
            network_id = network[ATTR_ID]
        else:
            network = Network(Client(loop=hass.loop), uid=network_id)

        yield from network.async_request()

    hass.async_add_job(async_setup_network)


@asyncio.coroutine
def async_setup_with_network(network, hass, config, async_add_entities,
                             discovery_info):
    """Set up when the Network UID is known."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    stations_list = config.get(CONF_STATIONS_LIST, [])
    radius = config.get(CONF_RADIUS, 0)
    if not hass.config.units.is_metric:
        radius = distance.convert(radius, LENGTH_FEET, LENGTH_METERS)

    async_track_time_interval(hass, network.async_refresh, SCAN_INTERVAL)

    if radius > 0:
        @asyncio.coroutine
        def get_nearest_stations(now=None):
            yield from network.async_refresh()
            yield from asyncio.sleep(15)
            entities = []
            for station, _ in network.stations.near(latitude, longitude):
                dist = location.distance(latitude, longitude,
                                         station[ATTR_LATITUDE],
                                         station[ATTR_LONGITUDE])
                if dist > radius:
                    break
                entities.append(CityBikesStationSensor(
                                network.id, station[ATTR_ID]))
            async_add_entities(entities, True)

        hass.async_add_job(get_nearest_stations)
    else:
        @asyncio.coroutine
        def get_stations_by_id(now=None):
            yield from network.async_refresh()
            yield from asyncio.sleep(30)
            entities = []
            for station in network.stations:
                if station[ATTR_ID] in stations_list:
                    entities.append(CityBikesStationSensor(
                                    network.id, station[ATTR_ID]))
                    continue
                if ATTR_EXTRA in station:
                    if ATTR_UID in station[ATTR_EXTRA]:
                        uid = str(station[ATTR_EXTRA][ATTR_UID])
                        if uid in stations_list:
                            entities.append(CityBikesStationSensor(network.id,
                                station[ATTR_ID]))
            async_add_entities(entities, True)

        hass.async_add_job(get_stations_by_id)


class CityBikesNetwork:
    """Thin wrapper around a CityBikes network object."""

    def __init__(self, network):
        self._network = network
        self._stations = []

    @property
    def id(self):
        return self._network['id']

    @property
    def stations(self):
        return self._stations

    @Throttle(SCAN_INTERVAL)
    @asyncio.coroutine
    def async_refresh(self, now=None):
        """Refresh the state of the network."""
        yield from self._network.async_request()
        self._stations = self._network.stations


class CityBikesStationSensor(Entity):
    """CityBikes API Sensor."""

    def __init__(self, network_id, station_id):
        """Initialize the sensor."""
        self._network_id = network_id
        self._station_id = station_id
        self._station_data = {}

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
        return "{} {}".format(self._network_id, self._station_id)

    @property
    def hidden(self):
        """Return whether the sensor should be hidden."""
        return self.state == STATE_UNKNOWN

    @asyncio.coroutine
    def async_update(self):
        """Update device state."""
        for station in MONITORED_NETWORKS[self._network_id].stations:
            if station[ATTR_ID] == self._station_id:
                self._station_data = station
                break
            if ATTR_EXTRA in station:
                if ATTR_UID in station[ATTR_EXTRA]:
                    uid = str(station[ATTR_EXTRA][ATTR_UID])
                    if uid == self._station_id:
                        self._station_data = station
                        break

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        try:
            return {
                ATTR_ATTRIBUTION: CITYBIKES_ATTRIBUTION,
                ATTR_UID: self._station_data[ATTR_EXTRA][ATTR_UID],
                ATTR_LATITUDE: self._station_data[ATTR_LATITUDE],
                ATTR_LONGITUDE: self._station_data[ATTR_LONGITUDE],
                ATTR_EMPTY_SLOTS: self._station_data[ATTR_EMPTY_SLOTS],
                ATTR_FRIENDLY_NAME: self._station_data[ATTR_STATION_NAME],
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
