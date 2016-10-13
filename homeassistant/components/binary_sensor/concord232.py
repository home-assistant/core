"""
Support for exposing Concord232 elements as sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.concord232/
"""

import logging

import threading

import time

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, SENSOR_CLASSES)
from homeassistant.const import (CONF_HOST, CONF_PORT)

import homeassistant.helpers.config_validation as cv

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


# pylint: disable=too-many-locals
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Concord232 binary sensor platform."""
    from concord232 import client as concord232_client

    def get_opening_type(zone):
        """Helper function to try to guess sensor type frm name."""
        _LOGGER.debug("get_opening_type by name: %s ", zone["name"])
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

    try:
        client = concord232_client.Client('http://{}:{}'.format(host, port))
        zones = client.list_zones()
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error('Unable to connect to Concord232: %s', str(ex))
        return False

    for zone in zones:
        _LOGGER.info('Loading Zone found: %s', zone['name'])

    zone_sensors = {
        zone['number']: Concord232ZoneSensor(
            zone,
            zone_types.get(zone['number'], get_opening_type(zone)))
        for zone in zones
        if zone['number'] not in exclude}
    _LOGGER.info(zone_sensors)

    if zone_sensors:
        add_devices(zone_sensors.values())
        watcher = Concord232Watcher(client, zone_sensors)
        watcher.start()
    else:
        _LOGGER.warning("No zones found on Concord232")
    return True


class Concord232ZoneSensor(BinarySensorDevice):
    """Representation of a Concord232 zone as a sensor."""

    def __init__(self, zone, zone_type):
        """Initialize the Concord232 binary sensor."""
        self._zone = zone
        self._zone_type = zone_type

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._zone_type

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._zone['name']

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # True means "faulted" or "open" or "abnormal state"
        return bool(self._zone['state'] == 'Normal')


class Concord232Watcher(threading.Thread):
    """Event listener thread to process NX584 events."""

    def __init__(self, client, zone_sensors):
        """Initialize Concord232 watcher thread."""
        super(Concord232Watcher, self).__init__()
        self.daemon = True
        self._client = client
        self._zone_sensors = zone_sensors

    def _process_events(self, events):
        for event in events:
            zone = event['number']
            zone_sensor = self._zone_sensors.get(zone)
            _LOGGER.debug("Zone %s detected as %s ", zone, zone_sensor)
            # pylint: disable=protected-access
            if not zone_sensor:
                return
            _LOGGER.debug("Zone State: %s", event['state'])
            zone_sensor._zone['state'] = event['state']
            zone_sensor.update_ha_state()

    def run(self):
        """Run the watcher."""
        while True:
            try:
                events = self._client.list_zones()
                if events:
                    self._process_events(events)
                time.sleep(1)
            except requests.exceptions.ConnectionError:
                _LOGGER.error("Failed to reach Concord232 server")
                time.sleep(10)
