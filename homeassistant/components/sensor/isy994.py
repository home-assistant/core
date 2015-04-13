""" Support for ISY994 sensors. """
# system imports
import logging

# homeassistant imports
from homeassistant.components.isy994 import ISY, ISYDeviceABC, SENSOR_STRING
from homeassistant.const import (STATE_OPEN, STATE_CLOSED, STATE_HOME,
                                 STATE_NOT_HOME, STATE_ON, STATE_OFF)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the isy994 platform. """
    logger = logging.getLogger(__name__)
    devs = []
    # verify connection
    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # import weather
    if ISY.climate is not None:
        for prop in ISY.climate._id2name:
            if prop is not None:
                node = WeatherPseudoNode('ISY.weather.' + prop, prop,
                                         getattr(ISY.climate, prop),
                                         getattr(ISY.climate, prop + '_units'))
                devs.append(ISYSensorDevice(node))

    # import sensor nodes
    for node in ISY.nodes:
        if SENSOR_STRING in node.name:
            devs.append(ISYSensorDevice(node, [STATE_ON, STATE_OFF]))

    # import sensor programs
    for (folder_name, states) in (
            ('HA.locations', [STATE_HOME, STATE_NOT_HOME]),
            ('HA.sensors', [STATE_OPEN, STATE_CLOSED]),
            ('HA.states', [STATE_ON, STATE_OFF])):
        try:
            folder = ISY.programs['My Programs'][folder_name]
        except KeyError:
            # folder does not exist
            pass
        else:
            for dtype, name, node_id in folder.children:
                node = folder[node_id].leaf
                devs.append(ISYSensorDevice(node, states))

    add_devices(devs)


class WeatherPseudoNode(object):
    """ This class allows weather variable to act as regular nodes. """

    def __init__(self, device_id, name, status, units=None):
        self._id = device_id
        self.name = name
        self.status = status
        self.units = units


class ISYSensorDevice(ISYDeviceABC):
    """ represents a isy sensor within home assistant. """

    _domain = 'sensor'

    def __init__(self, node, states=[]):
        super().__init__(node)
        self._states = states
