"""
homeassistant.components.sensor.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MySensors sensors.

Config:
  sensor:
    - platform: mysensors
      port: '/dev/ttyACM0'
"""
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.pymysensors.mysensors.mysensors as mysensors
import homeassistant.external.pymysensors.mysensors.const as const
from homeassistant.helpers.entity import Entity

from homeassistant.const import ATTR_BATTERY_LEVEL

CONF_PORT = "port"

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the mysensors platform. """

    devices = {}    # keep track of devices added to HA

    def sensor_update(update_type, nid):
        """ Callback for sensor updates from the MySensors gateway. """
        sensor = gateway.sensors[nid]
        if sensor.sketch_name is None:
            return
        if nid not in devices:
            devices[nid] = MySensorsNode(sensor.sketch_name)
            add_devices([devices[nid]])

        devices[nid].battery_level = sensor.battery_level
        for child_id, child in sensor.children.items():
            devices[nid].update_child(child_id, child)

    port = config.get(CONF_PORT)
    if port is None:
        _LOGGER.error("Missing required key 'port'")
        return False

    gateway = mysensors.SerialGateway(port, sensor_update)
    gateway.start()


class MySensorsNode(Entity):
    """ Represents a MySensors node. """
    def __init__(self, name):
        self._name = name
        self.battery_level = 0
        self.children = {}

    @property
    def name(self):
        """ The name of this sensor. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return ''

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        attrs = {}
        attrs[ATTR_BATTERY_LEVEL] = self.battery_level

        for child in self.children.values():
            for value_type, value in child.values.items():
                attrs[value_type] = value
        return attrs

    def update_child(self, child_id, child):
        """ Sets the values of a child sensor. """
        self.children[child_id] = MySensorsChildSensor(
            const.Presentation(child.type).name,
            {const.SetReq(t).name: v for t, v in child.values.items()})


class MySensorsChildSensor():
    """ Represents a MySensors child sensor. """
    # pylint: disable=too-few-public-methods
    def __init__(self, child_type, values):
        self.type = child_type
        self.values = values
