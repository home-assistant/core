"""
Support for ISY994 covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.isy994/
"""
import logging
from typing import Callable  # noqa

from homeassistant.components.cover import CoverDevice, DOMAIN
from homeassistant.components.isy994 import (ISY994_NODES, ISY994_PROGRAMS,
                                             KEY_STATUS, KEY_ACTIONS,
                                             ISYDevice)
from homeassistant.const import (
    STATE_OPEN, STATE_CLOSED, STATE_OPENING, STATE_CLOSING, STATE_UNKNOWN)
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    0: STATE_CLOSED,
    101: STATE_UNKNOWN,
    102: 'stopped',
    103: STATE_CLOSING,
    104: STATE_OPENING
}


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 cover platform."""
    devices = []
    for node in hass.data[ISY994_NODES][DOMAIN]:
        devices.append(ISYCoverDevice(node))

    for program in hass.data[ISY994_PROGRAMS].get(DOMAIN, []):
        try:
            status = program[KEY_STATUS]
            actions = program[KEY_ACTIONS]
            assert actions.dtype == 'program', 'Not a program'
        except (AttributeError, KeyError, AssertionError):
            _LOGGER.warning("Program entity '%s' not loaded due to"
                            "incompatible folder structure.", program.name)
        else:
            devices.append(ISYCoverProgram(program.name, status, actions))

    add_devices(devices)


class ISYCoverDevice(ISYDevice, CoverDevice):
    """Representation of an ISY994 cover device."""

    def __init__(self, node: object):
        """Initialize the ISY994 cover device."""
        ISYDevice.__init__(self, node)

    @property
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        return sorted((0, self.value, 100))[1]

    @property
    def is_closed(self) -> bool:
        """Get whether the ISY994 cover device is closed."""
        return self.state == STATE_CLOSED

    @property
    def state(self) -> str:
        """Get the state of the ISY994 cover device."""
        if self.is_unknown():
            return None
        else:
            return VALUE_TO_STATE.get(self.value, STATE_OPEN)

    def open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover device."""
        if not self._node.on(val=100):
            _LOGGER.error("Unable to open the cover")

    def close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover device."""
        if not self._node.off():
            _LOGGER.error("Unable to close the cover")


class ISYCoverProgram(ISYCoverDevice):
    """Representation of an ISY994 cover program."""

    def __init__(self, name: str, node: object, actions: object) -> None:
        """Initialize the ISY994 cover program."""
        ISYCoverDevice.__init__(self, node)
        self._name = name
        self._actions = actions

    @property
    def state(self) -> str:
        """Get the state of the ISY994 cover program."""
        return STATE_CLOSED if bool(self.value) else STATE_OPEN

    def open_cover(self, **kwargs) -> None:
        """Send the open cover command to the ISY994 cover program."""
        if not self._actions.runThen():
            _LOGGER.error("Unable to open the cover")

    def close_cover(self, **kwargs) -> None:
        """Send the close cover command to the ISY994 cover program."""
        if not self._actions.runElse():
            _LOGGER.error("Unable to close the cover")
