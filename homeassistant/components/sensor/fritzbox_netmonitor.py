"""
Support for monitoring the local system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.systemmonitor/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_RESOURCES, CONF_TYPE)
from homeassistant.components import group
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['fritzconnection==0.6']

GROUP_NAME_ALL_DEVICES = 'fritz status'
ENTITY_ID_ALL_DEVICES = group.ENTITY_ID_FORMAT.format('fritz_status')

CONF_DEFAULT_IP = '169.254.1.1'  # This IP is valid for all FRITZ!Box routers.

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): cv.string,
})

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'is_linked': ['Link active', '', 'mdi:web'],
    'is_connected': ['Connection status', '', 'mdi:web'],
    'wan_access_type': ['Connection type', '', 'mdi:web'],
    'external_ip': ['External IP address', '', 'mdi:server-network'],
    'uptime': ['Uptime', 's', 'mdi:clock'],
    'bytes_sent': ['Bytes sent', 'bytes', 'mdi:server-network'],
    'bytes_received': ['Bytes received', 'bytes', 'mdi:server-network'],
    'transmission_rate_up': ['Upstream', 'bytes/s', 'mdi:server-network'],
    'transmission_rate_down': ['Downstream', 'bytes/s', 'mdi:server-network'],

    'max_byte_rate_up': ['Maximum upstream-rate', 'bytes/s',
                         'mdi:server-network'],
    'max_byte_rate_down': ['Maximum downstream-rate', 'bytes/s',
                           'mdi:server-network'],
    'max_bit_rate_up': ['Maximum upstream-rate', 'bits/s',
                        'mdi:server-network'],
    'max_bit_rate_down': ['Maximum downstream-rate', 'bits/s',
                          'mdi:server-network'],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the fritzbox monitor sensors."""
    # pylint: disable=import-error
    import fritzconnection as fc

    host = config[CONF_HOST]

    try:
        fstatus = fc.FritzStatus(address=host)
    except (ValueError, TypeError):
        fstatus = None

    if fstatus is None:
        _LOGGER.error('Failed to establish connection to FRITZ!Box '
                      'with IP: %s', host)
        return 1
    else:
        _LOGGER.info('Successfully connected to FRITZ!Box')

    devices = []
    for resource in config[CONF_RESOURCES]:
        if 'arg' not in resource:
            resource['arg'] = ''
        devices.append(FritzboxMonitorSensor(fstatus,
                                             resource[CONF_TYPE],
                                             resource['arg']))

    add_devices(devices)

    entity_ids = (dev.entity_id for dev in devices)
    group.Group.create_group(hass, GROUP_NAME_ALL_DEVICES, entity_ids, False)


class FritzboxMonitorSensor(Entity):
    """Implementation of a fritzbox monitor sensor."""

    def __init__(self, fstatus, sensor_type, argument=''):
        """Initialize the sensor."""
        self._name = '{} {}'.format(SENSOR_TYPES[sensor_type][0], argument)
        self.argument = argument
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._fstatus = fstatus
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name.rstrip()

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest system information."""
        if self.type == 'is_linked':
            self._state = self._fstatus.is_linked
        elif self.type == 'is_connected':
            self._state = self._fstatus.is_connected
        elif self.type == 'wan_access_type':
            self._state = self._fstatus.wan_access_type
        elif self.type == 'external_ip':
            self._state = self._fstatus.external_ip
        elif self.type == 'uptime':
            self._state = self._fstatus.uptime
        elif self.type == 'bytes_sent':
            self._state = self._fstatus.bytes_sent
        elif self.type == 'bytes_received':
            self._state = self._fstatus.bytes_received
        elif self.type == 'transmission_rate_up':
            self._state = self._fstatus.transmission_rate[0]
        elif self.type == 'transmission_rate_down':
            self._state = self._fstatus.transmission_rate[1]
        elif self.type == 'max_byte_rate_up':
            self._state = self._fstatus.max_byte_rate[0]
        elif self.type == 'max_byte_rate_down':
            self._state = self._fstatus.max_byte_rate[1]
        elif self.type == 'max_bit_rate_up':
            self._state = self._fstatus.max_bit_rate[0]
        elif self.type == 'max_bit_rate_down':
            self._state = self._fstatus.max_bit_rate[1]
