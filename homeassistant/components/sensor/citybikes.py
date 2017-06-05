"""
Sensor for the CityBikes data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.citybikes/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE,
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_FRIENDLY_NAME,
    LENGTH_METERS, LENGTH_FEET)
from homeassistant.helpers.entity import Entity
from homeassistant.util import (
    Throttle, slugify, location, distance)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-citybikes==0.1.3']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=12)  # Arbitrary
DOMAIN = 'citybikes'
CONF_NETWORK = 'network'
CONF_RADIUS = 'radius'
CONF_STATIONS_LIST = 'stations'
ATTR_STATION_ID = 'id'
ATTR_STATION_UID = 'id'
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


def _filter_stations(network, radius, latitude, longitude, stations_list):
    if radius > 0:
        for station, dist in network.stations.near(latitude, longitude):
            # 'dist' is in weird units, let's calculate again
            dist = location.distance(latitude, longitude,
                                     station[ATTR_LATITUDE],
                                     station[ATTR_LONGITUDE])
            if dist > radius:
                break
            yield station
    else:
        for station in network.stations:
            if station['id'] in stations_list:
                yield station
                continue
            if 'extra' in station:
                if 'uid' in station['extra']:
                    if str(station['extra']['uid']) in stations_list:
                        yield station


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the CityBikes platform."""
    from citybikes import Client, Network

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    network_uid = config.get(CONF_NETWORK)
    if not network_uid:
        network = Client().networks.near(latitude, longitude)[0][0]
    else:
        network = Network(Client(), uid=network_uid)

    stations_list = config.get(CONF_STATIONS_LIST, [])
    radius = config.get(CONF_RADIUS, 0)
    if not hass.config.units.is_metric:
        radius = distance.convert(radius, LENGTH_FEET, LENGTH_METERS)
    poller = CityBikesNetworkPoller(network)

    add_devices(CityBikesStationSensor(poller, station,
                                       config.get(CONF_NAME, DOMAIN))
                for station in _filter_stations(network, radius, latitude,
                                                longitude, stations_list))


class CityBikesNetworkPoller(object):
    """A wrapper around a CityBikes Network object."""

    def __init__(self, network):
        """Initialize the poller."""
        self._network = network

    def get(self, station_id, update=True):
        """Return the station with the given id."""
        if update:
            self._update()
        for station in self._network.stations:
            if station[ATTR_STATION_ID] == station_id:
                return station

    @Throttle(SCAN_INTERVAL)
    def _update(self):
        """Update the state of the network."""
        self._network.request()


class CityBikesStationSensor(Entity):
    """CityBikes API Sensor."""

    def __init__(self, poller, station, base_name):
        """Initialize the sensor."""
        self._poller = poller
        self._base_name = base_name
        self._update(station)

    def _update(self, station):
        self._id = station[ATTR_STATION_ID]
        self._uid = station[ATTR_EXTRA]['uid'] if ATTR_EXTRA in station \
            and 'uid' in station[ATTR_EXTRA] \
            else None
        self._latitude = station[ATTR_LATITUDE]
        self._longitude = station[ATTR_LONGITUDE]
        self._empty_slots = station[ATTR_EMPTY_SLOTS]
        self._free_bikes = station[ATTR_FREE_BIKES]
        self._timestamp = station[ATTR_TIMESTAMP]
        self._friendly_name = station[ATTR_STATION_NAME]
        self._name = slugify("{}_{}".format(self._base_name,
                                            station[ATTR_STATION_NAME]))

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._free_bikes

    def update(self):
        """Update device state."""
        self._update(self._poller.get(self._id))

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CITYBIKES_ATTRIBUTION,
            ATTR_STATION_ID: self._id,
            ATTR_STATION_UID: self._uid,
            ATTR_LATITUDE: self._latitude,
            ATTR_LONGITUDE: self._longitude,
            ATTR_EMPTY_SLOTS: self._empty_slots,
            ATTR_FREE_BIKES: self._free_bikes,
            ATTR_TIMESTAMP: self._timestamp,
            ATTR_FRIENDLY_NAME: self._friendly_name,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'bikes'

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:bike'
