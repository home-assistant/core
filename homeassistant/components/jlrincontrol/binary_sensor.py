"""Add Support for JLR Incontrol Binary Sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from . import JLREntity, RESOURCES

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the JLR Binary sensors."""
    if discovery_info is None:
        return
    add_devices([JLRSensor(hass, *discovery_info)])


class JLRSensor(JLREntity, BinarySensorDevice):
    """Representation of a JLR sensor."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        _LOGGER.debug('Getting state of %s binary sensor' % self._attribute)
        val = self._get_vehicle_status(self.vehicle.info.get('vehicleStatus'))
        if val is None:
            return val
        elif val:
            val = val[self._attribute]
        else:
            return None

        if self._attribute in ['DOOR_IS_ALL_DOORS_LOCKED']:
            if val == 'FALSE':
                return True
            else:
                return False
        else:
            return val

    def _get_vehicle_status(self, vehicle):
        dict_only = {}
        for el in vehicle:
            dict_only[el.get('key')] = el.get('value')
        return dict_only

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return RESOURCES[self._attribute][3]

    @property
    def icon(self):
        """Return the icon."""
        return RESOURCES[self._attribute][2]
