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

SOMFY = 0x47
SOMFY_ZRTSI = 0x5a52
SOMFY_ZRTSI_CONTROLLER = (SOMFY, SOMFY_ZRTSI)
WORKAROUND = 'workaround'

DEVICE_MAPPINGS = {
    SOMFY_ZRTSI_CONTROLLER: WORKAROUND
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Z-Wave roller shutters."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]

    if value.command_class != zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL:
        return
    if value.index != 0:
        return

    value.set_change_verified(False)
    add_devices([ZwaveRollershutter(value)])


class ZwaveRollershutter(zwave.ZWaveDeviceEntity, RollershutterDevice):
    """Representation of an Zwave roller shutter."""

    def __init__(self, value):
        """Initialize the zwave rollershutter."""
        import libopenzwave
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._lozwmgr = libopenzwave.PyManager()
        self._lozwmgr.create()
        self._node = value.node
        self._current_position = None
        self._workaround = None
        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)
        if (value.node.manufacturer_id.strip() and
                value.node.product_id.strip()):
            specific_sensor_key = (int(value.node.manufacturer_id, 16),
                                   int(value.node.product_type, 16))

            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND:
                    _LOGGER.debug("Controller without positioning feedback")
                    self._workaround = 1

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id or \
           self._value.node == value.node:
            self.update_properties()
            self.update_ha_state()
            _LOGGER.debug("Value changed on network %s", value)

    def update_properties(self):
        """Callback on data change for the registered node/value pair."""
        # Position value
        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL).values():
            if value.command_class == \
               zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL and \
               value.label == 'Level':
                self._current_position = value.data

    @property
    def current_position(self):
        """Return the current position of Zwave roller shutter."""
        if not self._workaround:
            if self._current_position is not None:
                if self._current_position <= 5:
                    return 100
                elif self._current_position >= 95:
                    return 0
                else:
                    return 100 - self._current_position

    def move_up(self, **kwargs):
        """Move the roller shutter up."""
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL)
                      .values()):
            if value.command_class == \
               zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL and value.label == \
               'Open' or value.command_class == \
               zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL and value.label == \
               'Down':
                self._lozwmgr.pressButton(value.value_id)
                break

    def move_down(self, **kwargs):
        """Move the roller shutter down."""
        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL).values():
            if value.command_class == \
               zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL and value.label == \
               'Up' or value.command_class == \
               zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL and value.label == \
               'Close':
                self._lozwmgr.pressButton(value.value_id)
                break

    def move_position(self, position, **kwargs):
        """Move the roller shutter to a specific position."""
        self._node.set_dimmer(self._value.value_id, 100 - position)

    def stop(self, **kwargs):
        """Stop the roller shutter."""
        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL).values():
            if value.command_class == \
               zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL and value.label == \
               'Open' or value.command_class == \
               zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL and value.label == \
               'Down':
                self._lozwmgr.releaseButton(value.value_id)
                break
