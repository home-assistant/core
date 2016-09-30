"""
Support for Zwave garage door components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/garagedoor.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.garage_door import DOMAIN
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
from homeassistant.components.garage_door import GarageDoorDevice

COMMAND_CLASS_SWITCH_BINARY = 0x25  # 37
COMMAND_CLASS_BARRIER_OPERATOR = 0x66  # 102
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Z-Wave garage door device."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]

    if value.command_class != zwave.const.COMMAND_CLASS_SWITCH_BINARY and \
       value.command_class != zwave.const.COMMAND_CLASS_BARRIER_OPERATOR:
        return
    if value.type != zwave.const.TYPE_BOOL:
        return
    if value.genre != zwave.const.GENRE_USER:
        return

    value.set_change_verified(False)
    add_devices([ZwaveGarageDoor(value)])


class ZwaveGarageDoor(zwave.ZWaveDeviceEntity, GarageDoorDevice):
    """Representation of an Zwave garage door device."""

    def __init__(self, value):
        """Initialize the zwave garage door."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._state = value.data
        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id:
            self._state = value.data
            self.update_ha_state()
            _LOGGER.debug("Value changed on network %s", value)

    @property
    def is_closed(self):
        """Return the current position of Zwave garage door."""
        return not self._state

    def close_door(self):
        """Close the garage door."""
        self._value.data = False

    def open_door(self):
        """Open the garage door."""
        self._value.data = True
