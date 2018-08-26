"""
Support for texecom zone states- represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.texecom/
"""

import logging

from homeassistant.core import callback
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.texecom import (
    CONF_ZONE_NAME, CONF_ZONE_NUMBER, CONF_ZONE_TYPE,
    ZONE_SCHEMA, SIGNAL_ZONE_UPDATE)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect)


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['texecom']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Texecom binary sensor devices."""
    _LOGGER.info('Setting Up Binary Sensors')
    configured_zones = discovery_info['zones']
    devices = []
    for index in configured_zones:
        device_config_data = ZONE_SCHEMA(configured_zones[index])

        device = TexecomBinarySensor(
            hass,
            device_config_data[CONF_ZONE_NUMBER],
            device_config_data[CONF_ZONE_NAME],
            device_config_data[CONF_ZONE_TYPE],
        )
        devices.append(device)

    async_add_entities(devices)


class TexecomBinarySensor(BinarySensorDevice):
    """Representation of an Texecom Binary Sensor."""

    def __init__(self, name, zone_number, zone_name, zone_type):
        """Initialize the device."""
        self._number = zone_number
        self._name = zone_name
        self._sensor_type = zone_type
        self._state = 'false'

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_ZONE_UPDATE, self._update_callback)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return the name of the device."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @callback
    def _update_callback(self, data):
        """Update the zone's state, if needed."""
        _LOGGER.debug('Attempting to Update Zone %s', self._name)
        state = data[int(self._number)]
        _LOGGER.debug('The new state is %s', state)

        if state == '0':
            _LOGGER.debug('Setting zone state to false')
            self._state = False
        elif state == '1':
            _LOGGER.debug('Setting zone state to true')
            self._state = True
        else:
            _LOGGER.debug('Unknown state assuming tamper')
            self._state = True

        _LOGGER.debug('New Zone State is %s', self._state)
        self.async_schedule_update_ha_state()
