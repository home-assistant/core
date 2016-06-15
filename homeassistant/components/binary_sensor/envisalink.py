"""
Support for Envisalink zone states- represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.envisalink/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.envisalink import (EVL_CONTROLLER,
                                                 EnvisalinkDevice,
                                                 SIGNAL_ZONE_UPDATE)
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.util import convert

REQUIREMENTS = ['pydispatcher==2.0.5']
DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Envisalink sensor devices."""
    _configured_zones = discovery_info['zones']
    add_devices_callback(
        EnvisalinkBinarySensor(zoneNum,
                               convert(_configured_zones[zoneNum]['name'],
                                       str,
                                       str.format("Zone #{0}", zoneNum)),
                               convert(_configured_zones[zoneNum]['type'],
                                       str,
                                       "opening"),
                               EVL_CONTROLLER.alarm_state['zone'][zoneNum],
                               EVL_CONTROLLER)
        for zoneNum in _configured_zones)


class EnvisalinkBinarySensor(EnvisalinkDevice, BinarySensorDevice):
    """Representation of an envisalink Binary Sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, zoneNumber, zoneName, zoneType, info, controller):
        """Initialize the binary_sensor."""
        from pydispatch import dispatcher
        self._zone_type = zoneType
        self._zone_number = zoneNumber

        _LOGGER.info('Setting up zone: ' + zoneName)
        EnvisalinkDevice.__init__(self, zoneName, info, controller)
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
            self.update_ha_state()
