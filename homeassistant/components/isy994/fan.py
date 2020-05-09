"""Support for ISY994 fans."""
from typing import Callable

from homeassistant.components.fan import (
    DOMAIN as FAN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.helpers.typing import ConfigType

from . import ISY994_NODES, ISY994_PROGRAMS
from .const import _LOGGER
from .entity import ISYNodeEntity, ISYProgramEntity

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


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the ISY994 fan platform."""
    devices = []

    for node in hass.data[ISY994_NODES][FAN]:
        devices.append(ISYFanEntity(node))

    for name, status, actions in hass.data[ISY994_PROGRAMS][FAN]:
        devices.append(ISYFanProgramEntity(name, status, actions))

    add_entities(devices)


class ISYFanEntity(ISYNodeEntity, FanEntity):
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
        self._node.turn_on(val=STATE_TO_VALUE.get(speed, 255))

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Send the turn on command to the ISY994 fan device."""
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 fan device."""
        self._node.turn_off()

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED


class ISYFanProgramEntity(ISYProgramEntity, FanEntity):
    """Representation of an ISY994 fan program."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return VALUE_TO_STATE.get(self.value)

    @property
    def is_on(self) -> bool:
        """Get if the fan is on."""
        return self.value != 0

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to ISY994 fan program."""
        if not self._actions.run_then():
            _LOGGER.error("Unable to turn off the fan")

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Send the turn off command to ISY994 fan program."""
        if not self._actions.run_else():
            _LOGGER.error("Unable to turn on the fan")
