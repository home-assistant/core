"""
Support for ISY994 lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.isy994/
"""
import logging
from typing import Callable

from homeassistant.components.light import (
    Light, SUPPORT_BRIGHTNESS, DOMAIN)
from homeassistant.components.isy994 import ISY994_NODES, ISYDevice
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 light platform."""
    devices = []
    for node in hass.data[ISY994_NODES][DOMAIN]:
        devices.append(ISYLightDevice(node))

    add_devices(devices)


class ISYLightDevice(ISYDevice, Light):
    """Representation of an ISY994 light devie."""

    def __init__(self, node: object) -> None:
        """Initialize the ISY994 light device."""
        super().__init__(node)

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 light is on."""
        return self.value > 0

    @property
    def brightness(self) -> float:
        """Get the brightness of the ISY994 light."""
        return self.value

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 light device."""
        if not self._node.off():
            _LOGGER.debug("Unable to turn off light")

    def turn_on(self, brightness=None, **kwargs) -> None:
        """Send the turn on command to the ISY994 light device."""
        if not self._node.on(val=brightness):
            _LOGGER.debug("Unable to turn on light")

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
