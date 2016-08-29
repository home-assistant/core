"""
Support for ISY994 locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/isy994/
"""
import logging

from homeassistant.components.isy994 import (
    HIDDEN_STRING, ISY, SENSOR_STRING, ISYDeviceABC)
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED


# The frontend doesn't seem to fully support the open and closed states yet.
# Once it does, the HA.doors programs should report open and closed instead of
# off and on. It appears that on should be unlocked and off should be locked.


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ISY994 platform."""
    # pylint: disable=too-many-locals
    logger = logging.getLogger(__name__)
    devs = []
    # verify connection
    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # Import not dimmable nodes and groups
    for (path, node) in ISY.nodes:
        if not node.dimmable and SENSOR_STRING not in node.name:
            if HIDDEN_STRING in path:
                node.name += HIDDEN_STRING
            devs.append(ISYLockDevice(node))

    # Import ISY doors programs
    for folder_name, states in ('HA.locks', [STATE_UNLOCKED, STATE_LOCKED]):
        try:
            folder = ISY.programs['My Programs'][folder_name]
        except KeyError:
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


class ISYLockDevice(ISYDeviceABC):
    """Representation of an ISY lock."""

    _domain = 'locks'
    _dtype = 'binary'
    _states = [STATE_UNLOCKED, STATE_LOCKED]


class ISYProgramDevice(ISYLockDevice):
    """Representation of an ISY door."""

    _domain = 'lock'
    _dtype = 'binary'

    def __init__(self, name, node, actions, states):
        """Initialize the lock."""
        super().__init__(node)
        self._states = states
        self._name = name
        self.action_node = actions

    @property
    def is_locked(self):
        """Return if the lock is locked."""
        return self._states

    def unlock(self, **kwargs):
        """Unlock the device the device."""
        self.action_node.runThen()

    def lock(self, **kwargs):
        """Lock the device."""
        self.action_node.runElse()
