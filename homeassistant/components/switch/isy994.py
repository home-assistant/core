"""
homeassistant.components.switch.isy994
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for ISY994 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/isy994/
"""
import logging

from homeassistant.components.isy994 import (
    HIDDEN_STRING, ISY, SENSOR_STRING, ISYDeviceABC)
from homeassistant.const import STATE_OFF, STATE_ON  # STATE_OPEN, STATE_CLOSED


# The frontend doesn't seem to fully support the open and closed states yet.
# Once it does, the HA.doors programs should report open and closed instead of
# off and on. It appears that on should be open and off should be closed.


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the ISY994 platform. """
    # pylint: disable=too-many-locals
    logger = logging.getLogger(__name__)
    devs = []
    # verify connection
    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # import not dimmable nodes and groups
    for (path, node) in ISY.nodes:
        if not node.dimmable and SENSOR_STRING not in node.name:
            if HIDDEN_STRING in path:
                node.name += HIDDEN_STRING
            devs.append(ISYSwitchDevice(node))

    # import ISY doors programs
    for folder_name, states in (('HA.doors', [STATE_ON, STATE_OFF]),
                                ('HA.switches', [STATE_ON, STATE_OFF])):
        try:
            folder = ISY.programs['My Programs'][folder_name]
        except KeyError:
            # HA.doors folder does not exist
            pass
        else:
            for dtype, name, node_id in folder.children:
                if dtype is 'folder':
                    custom_switch = folder[node_id]
                    try:
                        actions = custom_switch['actions'].leaf
                        assert actions.dtype == 'program', 'Not a program'
                        node = custom_switch['status'].leaf
                    except (KeyError, AssertionError):
                        pass
                    else:
                        devs.append(ISYProgramDevice(name, node, actions,
                                                     states))

    add_devices(devs)


class ISYSwitchDevice(ISYDeviceABC):
    """ Represents as ISY light. """

    _domain = 'switch'
    _dtype = 'binary'
    _states = [STATE_ON, STATE_OFF]


class ISYProgramDevice(ISYSwitchDevice):
    """ Represents a door that can be manipulated. """

    _domain = 'switch'
    _dtype = 'binary'

    def __init__(self, name, node, actions, states):
        super().__init__(node)
        self._states = states
        self._name = name
        self.action_node = actions

    def turn_on(self, **kwargs):
        """ Turns the device on/closes the device. """
        self.action_node.runThen()

    def turn_off(self, **kwargs):
        """ Turns the device off/opens the device. """
        self.action_node.runElse()
