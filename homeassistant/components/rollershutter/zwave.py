"""
Support for Zwave roller shutter components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/rollershutter.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.rollershutter import DOMAIN
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
from homeassistant.components.rollershutter import RollershutterDevice

COMMAND_CLASS_SWITCH_MULTILEVEL = 0x26  # 38
COMMAND_CLASS_SWITCH_BINARY = 0x25  # 37

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Z-Wave roller shutters."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.ATTR_VALUE_ID]]

    if value.command_class != zwave.COMMAND_CLASS_SWITCH_MULTILEVEL:
        return
    if value.index != 0:
        return

    value.set_change_verified(False)
    add_devices([ZwaveRollershutter(value)])


class ZwaveRollershutter(zwave.ZWaveDeviceEntity, RollershutterDevice):
    """Representation of an Zwave roller shutter."""

    def __init__(self, value):
        """Initialize the zwave rollershutter."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._node = value.node
        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id:
            self.update_ha_state(True)
            _LOGGER.debug("Value changed on network %s", value)

    @property
    def current_position(self):
        """Return the current position of Zwave roller shutter."""
        return self._value.data

    def move_up(self, **kwargs):
        """Move the roller shutter up."""
        self._node.set_dimmer(self._value.value_id, 100)

    def move_down(self, **kwargs):
        """Move the roller shutter down."""
        self._node.set_dimmer(self._value.value_id, 0)

    def stop(self, **kwargs):
        """Stop the roller shutter."""
        for value in self._node.get_values(
                class_id=COMMAND_CLASS_SWITCH_BINARY).values():
            # Rollershutter will toggle between UP (True), DOWN (False).
            # It also stops the shutter if the same value is sent while moving.
            value.data = value.data
            break
