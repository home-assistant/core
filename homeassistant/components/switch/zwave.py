"""
Z-Wave platform that handles simple binary switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zwave/
"""
import logging
import time
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components import zwave
from homeassistant.components.zwave import workaround, async_setup_platform  # noqa # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


def get_device(value, **kwargs):
    """Create zwave entity device."""
    return ZwaveSwitch(value)


class ZwaveSwitch(zwave.ZWaveDeviceEntity, SwitchDevice):
    """Representation of a Z-Wave switch."""

    def __init__(self, value):
        """Initialize the Z-Wave switch device."""
        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self.refresh_on_update = (workaround.get_device_mapping(value) ==
                                  workaround.WORKAROUND_REFRESH_NODE_ON_UPDATE)
        self.last_update = time.perf_counter()
        self._state = self._value.data

    def update_properties(self):
        """Callback on data changes for node values."""
        self._state = self._value.data
        if self.refresh_on_update and \
                time.perf_counter() - self.last_update > 30:
            self.last_update = time.perf_counter()
            self._value.node.request_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._value.node.set_switch(self._value.value_id, True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._value.node.set_switch(self._value.value_id, False)
