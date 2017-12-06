"""
Support for ISY994 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.isy994/
"""
import logging
from typing import Callable  # noqa

from homeassistant.components.switch import SwitchDevice, DOMAIN
import homeassistant.components.isy994 as isy
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN
from homeassistant.helpers.typing import ConfigType  # noqa

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    False: STATE_OFF,
    True: STATE_ON,
}

UOM = ['2', '78']
STATES = [STATE_OFF, STATE_ON, 'true', 'false']


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 switch platform."""
    if isy.ISY is None or not isy.ISY.connected:
        _LOGGER.error('A connection has not been made to the ISY controller.')
        return False

    devices = []

    for node in isy.filter_nodes(isy.NODES, units=UOM,
                                 states=STATES):
        if not node.dimmable:
            devices.append(ISYSwitchDevice(node))

    for node in isy.GROUPS:
        devices.append(ISYSwitchDevice(node))

    for program in isy.PROGRAMS.get(DOMAIN, []):
        try:
            status = program[isy.KEY_STATUS]
            actions = program[isy.KEY_ACTIONS]
            assert actions.dtype == 'program', 'Not a program'
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYSwitchProgram(program.name, status, actions))

    add_devices(devices)


class ISYSwitchDevice(isy.ISYDevice, SwitchDevice):
    """Representation of an ISY994 switch device."""

    def __init__(self, node) -> None:
        """Initialize the ISY994 switch device."""
        isy.ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 device is in the on state."""
        return self.state == STATE_ON

    @property
    def state(self) -> str:
        """Get the state of the ISY994 device."""
        if self.is_unknown():
            return None
        else:
            return VALUE_TO_STATE.get(bool(self.value), STATE_UNKNOWN)

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch."""
        if not self._node.off():
            _LOGGER.debug('Unable to turn on switch.')

    def turn_on(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch."""
        if not self._node.on():
            _LOGGER.debug('Unable to turn on switch.')


class ISYSwitchProgram(ISYSwitchDevice):
    """A representation of an ISY994 program switch."""

    def __init__(self, name: str, node, actions) -> None:
        """Initialize the ISY994 switch program."""
        ISYSwitchDevice.__init__(self, node)
        self._name = name
        self._actions = actions

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 switch program is on."""
        return bool(self.value)

    def turn_on(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch program."""
        if not self._actions.runThen():
            _LOGGER.error('Unable to turn on switch')

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch program."""
        if not self._actions.runElse():
            _LOGGER.error('Unable to turn off switch')
