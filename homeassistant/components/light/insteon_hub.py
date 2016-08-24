"""
Support for Insteon Hub lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/insteon_hub/
"""
from homeassistant.components.insteon_hub import (INSTEON, InsteonDevice)
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)

SUPPORT_INSTEON_HUB = SUPPORT_BRIGHTNESS

DEPENDENCIES = ['insteon_hub']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon Hub light platform."""
    devs = []
    for device in INSTEON.devices:
        if device.DeviceCategory == "Switched Lighting Control":
            devs.append(InsteonLightDevice(device))
        if device.DeviceCategory == "Dimmable Lighting Control":
            devs.append(InsteonDimmableDevice(device))
    add_devices(devs)


class InsteonLightDevice(InsteonDevice, Light):
    """A representation of a light device."""

    def __init__(self, node: object) -> None:
        """Initialize the device."""
        super(InsteonLightDevice, self).__init__(node)
        self._value = 0

    def update(self) -> None:
        """Update state of the device."""
        resp = self._node.send_command('get_status', wait=True)
        try:
            self._value = resp['response']['level']
        except KeyError:
            pass

    @property
    def is_on(self) -> None:
        """Return the boolean response if the node is on."""
        return self._value != 0

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if self._send_command('on'):
            self._value = 100

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        if self._send_command('off'):
            self._value = 0


class InsteonDimmableDevice(InsteonLightDevice):
    """A representation for a dimmable device."""

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return round(self._value / 100 * 255, 0)  # type: int

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_INSTEON_HUB

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        level = 100  # type: int
        if ATTR_BRIGHTNESS in kwargs:
            level = round(kwargs[ATTR_BRIGHTNESS] / 255 * 100, 0)  # type: int

        if self._send_command('on', level=level):
            self._value = level
