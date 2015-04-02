import homeassistant.external.pymysensors.mysensors as mysensors
from homeassistant.helpers.entity import Entity
import logging

#
# Config:
#  sensor:
#  platform: mysensors
#  gateway: serial
#  port: '/dev/ttyACM0'
#

from homeassistant.const import (
    ATTR_BATTERY_LEVEL )

_LOGGER = logging.getLogger(__name__)

devices = {}    # keep track of devices added to HA
gw = mysensors.Gateway();

def setup_platform(hass, config, add_devices, discovery_info=None):

    # Passed to pymysensors and called when a sensor is updated
    def sensor_update(type, nid, cid = None, value = None):
        s = gw.sensors[nid]
        if s.sketch_name is not None:
            if nid in devices:
                devices[nid]._battery_level = s.battery_level
                for c in s.children:
                    child = s.children[c]
                    devices[nid]._children[child.id] = MySensorsChildSensor(child.type, child.value)
            else:
                devices[nid] = MySensorsSensor(s.sketch_name)
                add_devices([devices[nid]])

    if config['gateway'] == 'serial':
        gw = mysensors.SerialGateway('/dev/ttyACM0', sensor_update)
    else:
        _LOGGER.error('mysensors gateway type: ' + config.gateway + ' not supported')

    gw.listen()


class MySensorsSensor(Entity):
    def __init__(self, name):
        self._name = name
        self._state = ''
        self._battery_level = 0
        self._children = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        attrs = {}
        attrs[ATTR_BATTERY_LEVEL] = self._battery_level
        
        for c in self._children.values():
            attrs[c._type] = c._value

        return attrs

    #def update(self):
        # get latest values from gateway

class MySensorsChildSensor():
    def __init__(self, type, value):
        self._type = type
        self._value = value