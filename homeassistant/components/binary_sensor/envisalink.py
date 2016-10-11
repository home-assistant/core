"""
Support for Envisalink zone states- represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.envisalink/
"""
import logging
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.envisalink import (EVL_CONTROLLER,
                                                 ZONE_SCHEMA,
                                                 CONF_ZONENAME,
                                                 CONF_ZONETYPE,
                                                 EnvisalinkDevice,
                                                 SIGNAL_ZONE_UPDATE)
from homeassistant.const import ATTR_LAST_TRIP_TIME

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup Envisalink binary sensor devices."""
    _configured_zones = discovery_info['zones']
    for zone_num in _configured_zones:
        _device_config_data = ZONE_SCHEMA(_configured_zones[zone_num])
        _device = EnvisalinkBinarySensor(
            zone_num,
            _device_config_data[CONF_ZONENAME],
            _device_config_data[CONF_ZONETYPE],
            EVL_CONTROLLER.alarm_state['zone'][zone_num],
            EVL_CONTROLLER)
        add_devices_callback([_device])


class EnvisalinkBinarySensor(EnvisalinkDevice, BinarySensorDevice):
    """Representation of an Envisalink binary sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, zone_number, zone_name, zone_type, info, controller):
        """Initialize the binary_sensor."""
        from pydispatch import dispatcher
        self._zone_type = zone_type
        self._zone_number = zone_number

        _LOGGER.debug('Setting up zone: ' + zone_name)
        EnvisalinkDevice.__init__(self, zone_name, info, controller)
        dispatcher.connect(self._update_callback,
                           signal=SIGNAL_ZONE_UPDATE,
                           sender=dispatcher.Any)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr[ATTR_LAST_TRIP_TIME] = self._info['last_fault']
        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._info['status']['open']

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._zone_type

    def _update_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self.hass.async_add_job(self.update_ha_state)
