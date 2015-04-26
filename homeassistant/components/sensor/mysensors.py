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

from homeassistant.const import (
    ATTR_BATTERY_LEVEL, EVENT_HOMEASSISTANT_STOP,
    TEMP_CELCIUS, TEMP_FAHRENHEIT,
    STATE_ON, STATE_OFF)

CONF_PORT = "port"

ATTR_NODE_ID = "node_id"
ATTR_CHILD_ID = "child_id"

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the mysensors platform. """

    devices = {}    # keep track of devices added to HA
    # Just assume celcius means that the user wants metric for now.
    # It may make more sense to make this a global config option in the future.
    is_metric = (hass.config.temperature_unit == TEMP_CELCIUS)

    def sensor_update(update_type, nid):
        """ Callback for sensor updates from the MySensors gateway. """
        _LOGGER.info("sensor_update %s: node %s", update_type, nid)
        sensor = gateway.sensors[nid]
        if sensor.sketch_name is None:
            return
        if nid not in devices:
            devices[nid] = {}

        node = devices[nid]
        new_devices = []
        for child_id, child in sensor.children.items():
            if child_id not in node:
                node[child_id] = {}
            for value_type, value in child.values.items():
                if value_type not in node[child_id]:
                    name = '{} {}.{}'.format(sensor.sketch_name, nid, child.id)
                    node[child_id][value_type] = \
                        MySensorsNodeValue(
                            nid, child_id, name, value_type, is_metric)
                    new_devices.append(node[child_id][value_type])
                else:
                    node[child_id][value_type].update_sensor(
                        value, sensor.battery_level)

        if new_devices:
            _LOGGER.info("adding new devices: %s", new_devices)
            add_devices(new_devices)

    port = config.get(CONF_PORT)
    if port is None:
        _LOGGER.error("Missing required key 'port'")
        return False

    gateway = mysensors.SerialGateway(port, sensor_update)
    gateway.start()
    gateway.metric = is_metric

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                         lambda event: gateway.stop())


class MySensorsNodeValue(Entity):
    """ Represents the value of a MySensors child node. """
    # pylint: disable=too-many-arguments
    def __init__(self, node_id, child_id, name, value_type, metric):
        self._name = name
        self.node_id = node_id
        self.child_id = child_id
        self.battery_level = 0
        self.value_type = value_type
        self.metric = metric
        self._value = ''

    @property
    def should_poll(self):
        """ MySensor gateway pushes its state to HA.  """
        return False

    @property
    def name(self):
        """ The name of this sensor. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._value

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity. """
        if self.value_type == const.SetReq.V_TEMP:
            return TEMP_CELCIUS if self.metric else TEMP_FAHRENHEIT
        elif self.value_type == const.SetReq.V_HUM or \
                self.value_type == const.SetReq.V_DIMMER or \
                self.value_type == const.SetReq.V_LIGHT_LEVEL:
            return '%'
        return None

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        return {
            ATTR_NODE_ID: self.node_id,
            ATTR_CHILD_ID: self.child_id,
            ATTR_BATTERY_LEVEL: self.battery_level,
        }

    def update_sensor(self, value, battery_level):
        """ Update a sensor with the latest value from the controller. """
        _LOGGER.info("%s value = %s", self._name, value)
        if self.value_type == const.SetReq.V_TRIPPED or \
           self.value_type == const.SetReq.V_ARMED:
            self._value = STATE_ON if int(value) == 1 else STATE_OFF
        else:
            self._value = value
        self.battery_level = battery_level
        self.update_ha_state()
