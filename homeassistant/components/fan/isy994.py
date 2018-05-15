"""
Support for ISY994 fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.isy994/
"""
import logging
from typing import Callable

from homeassistant.components.fan import (FanEntity, DOMAIN, SPEED_OFF,
                                          SPEED_LOW, SPEED_MEDIUM,
                                          SPEED_HIGH, SUPPORT_SET_SPEED)
from homeassistant.components.isy994 import (ISY994_NODES, ISY994_PROGRAMS,
                                             ISYDevice)
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    0: SPEED_OFF,
    63: SPEED_LOW,
    64: SPEED_LOW,
    190: SPEED_MEDIUM,
    191: SPEED_MEDIUM,
    255: SPEED_HIGH,
}

STATE_TO_VALUE = {}
for key in VALUE_TO_STATE:
    STATE_TO_VALUE[VALUE_TO_STATE[key]] = key


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 fan platform."""
    devices = []

    for node in hass.data[ISY994_NODES][DOMAIN]:
        devices.append(ISYFanDevice(node))

    for name, status, actions in hass.data[ISY994_PROGRAMS][DOMAIN]:
        devices.append(ISYFanProgram(name, status, actions))

    add_devices(devices)


class ISYFanDevice(ISYDevice, FanEntity):
    """Representation of an ISY994 fan device."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return VALUE_TO_STATE.get(self.value)

    @property
    def is_on(self) -> bool:
        """Get if the fan is on."""
        return self.value != 0

    def set_speed(self, speed: str) -> None:
        """Send the set speed command to the ISY994 fan device."""
        self._node.on(val=STATE_TO_VALUE.get(speed, 255))

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Send the turn on command to the ISY994 fan device."""
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 fan device."""
        self._node.off()

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED


class ISYFanProgram(ISYFanDevice):
    """Representation of an ISY994 fan program."""

    def __init__(self, name: str, node, actions) -> None:
        """Initialize the ISY994 fan program."""
        super().__init__(node)
        self._name = name
        self._actions = actions

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to ISY994 fan program."""
        if not self._actions.runThen():
            _LOGGER.error("Unable to turn off the fan")

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Send the turn off command to ISY994 fan program."""
        if not self._actions.runElse():
            _LOGGER.error("Unable to turn on the fan")

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0
