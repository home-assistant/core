"""
Support for exposing Concord232 elements as sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.concord232/
"""
import datetime

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, SENSOR_CLASSES)
from homeassistant.const import (CONF_HOST, CONF_PORT)

import homeassistant.helpers.config_validation as cv

from concord232 import client as concord232_client

import requests

import voluptuous as vol


REQUIREMENTS = ['concord232==0.14']

_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE_ZONES = 'exclude_zones'
CONF_ZONE_TYPES = 'zone_types'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = '5007'
DEFAULT_SSL = False

ZONE_TYPES_SCHEMA = vol.Schema({
    cv.positive_int: vol.In(SENSOR_CLASSES),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_EXCLUDE_ZONES, default=[]):
        vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_ZONE_TYPES, default={}): ZONE_TYPES_SCHEMA,
})

CONCORD232_GLOBAL = None

SCAN_INTERVAL = 1

DEFAULT_NAME = "Alarm"


# pylint: disable=too-many-locals
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Concord232 binary sensor platform."""

    def get_opening_type(zone):
        """Helper function to try to guess sensor type frm name."""
        if "MOTION" in zone["name"]:
            return "motion"
        if "KEY" in zone["name"]:
            return "safety"
        if "SMOKE" in zone["name"]:
            return "smoke"
        if "WATER" in zone["name"]:
            return "water"
        return "opening"

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    exclude = config.get(CONF_EXCLUDE_ZONES)
    zone_types = config.get(CONF_ZONE_TYPES)
    sensors = []

    try:
        global CONCORD232_GLOBAL
        if CONCORD232_GLOBAL is None:
            _LOGGER.debug('Initializing GLOBAL Client.')
            CONCORD232_GLOBAL = concord232_client.Client('http://{}:{}'
                                                         .format(host, port))
            CONCORD232_GLOBAL.zones = CONCORD232_GLOBAL.list_zones()
            CONCORD232_GLOBAL.last_zone_update = datetime.datetime.now()
        else:
            _LOGGER.debug('Found GLOBAL Client using it')

    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error('Unable to connect to Concord232: %s', str(ex))
        return False

    for zone in CONCORD232_GLOBAL.zones:
        _LOGGER.info('Loading Zone found: %s', zone['name'])
        if zone['number'] not in exclude:
            sensors.append(Concord232ZoneSensor(
                hass,
                CONCORD232_GLOBAL,
                zone,
                zone_types.get(zone['number'], get_opening_type(zone))))

        add_devices(sensors)

    return True


class Concord232ZoneSensor(BinarySensorDevice):
    """Representation of a Concord232 zone as a sensor."""

    def __init__(self, hass, client, zone, zone_type):
        """Initialize the Concord232 binary sensor."""
        self._hass = hass
        self._client = client
        self._zone = zone
        self._number = zone['number']
        self._zone_type = zone_type
        self.update()

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._zone_type

    @property
    def should_poll(self):
        """No polling needed."""
        return True

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._zone['name']

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # True means "faulted" or "open" or "abnormal state"
        return bool(self._zone['state'] == 'Normal')

    def update(self):
        """"Get updated stats from API."""
        last_update = datetime.datetime.now() - self._client.last_zone_update
        _LOGGER.debug("Zone: %s ", self._zone)
        if last_update > datetime.timedelta(seconds=1):
            self._client.zones = self._client.list_zones()
            self._client.last_zone_update = datetime.datetime.now()
            _LOGGER.debug("Updated from Zone: %s", self._zone['name'])

        if hasattr(self._client, 'zones'):
            self._zone = next((x for x in self._client.zones
                               if x['number'] == self._number), None)
