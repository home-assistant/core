"""
Support for Zwave cover components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.cover import DOMAIN
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
from homeassistant.components.cover import CoverDevice

SOMFY = 0x47
SOMFY_ZRTSI = 0x5a52
SOMFY_ZRTSI_CONTROLLER = (SOMFY, SOMFY_ZRTSI)
WORKAROUND = 'workaround'

DEVICE_MAPPINGS = {
    SOMFY_ZRTSI_CONTROLLER: WORKAROUND
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Z-Wave covers."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]

    if (value.command_class == zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL
            and value.index == 0):
        value.set_change_verified(False)
        add_devices([ZwaveRollershutter(value)])
    elif (value.command_class == zwave.const.COMMAND_CLASS_SWITCH_BINARY or
          value.command_class == zwave.const.COMMAND_CLASS_BARRIER_OPERATOR):
        if (value.type != zwave.const.TYPE_BOOL and
                value.genre != zwave.const.GENRE_USER):
            return
        value.set_change_verified(False)
        add_devices([ZwaveGarageDoor(value)])
    else:
        return


class ZwaveRollershutter(zwave.ZWaveDeviceEntity, CoverDevice):
    """Representation of an Zwave roller shutter."""

    def __init__(self, value):
        """Initialize the zwave rollershutter."""
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        # pylint: disable=no-member
        self._node = value.node
        self._open_id = None
        self._close_id = None
        self._current_position = None
        self._workaround = None
        if (value.node.manufacturer_id.strip() and
                value.node.product_id.strip()):
            specific_sensor_key = (int(value.node.manufacturer_id, 16),
                                   int(value.node.product_type, 16))

            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND:
                    _LOGGER.debug("Controller without positioning feedback")
                    self._workaround = 1

    def update_properties(self):
        """Callback on data changes for node values."""
        # Position value
        self._current_position = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL,
            label=['Level'], member='data')
        self._open_id = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL,
            label=['Open', 'Up'], member='value_id')
        self._close_id = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL,
            label=['Close', 'Down'], member='value_id')

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is None:
            return None
        if self.current_cover_position > 0:
            return False
        else:
            return True

    @property
    def current_cover_position(self):
        """Return the current position of Zwave roller shutter."""
        if not self._workaround:
            if self._current_position is not None:
                if self._current_position <= 5:
                    return 0
                elif self._current_position >= 95:
                    return 100
                else:
                    return self._current_position

    def open_cover(self, **kwargs):
        """Move the roller shutter up."""
        zwave.NETWORK.manager.pressButton(self._open_id)

    def close_cover(self, **kwargs):
        """Move the roller shutter down."""
        zwave.NETWORK.manager.pressButton(self._close_id)

    def set_cover_position(self, position, **kwargs):
        """Move the roller shutter to a specific position."""
        self._node.set_dimmer(self._value.value_id, position)

    def stop_cover(self, **kwargs):
        """Stop the roller shutter."""
        zwave.NETWORK.manager.releaseButton(self._open_id)


class ZwaveGarageDoor(zwave.ZWaveDeviceEntity, CoverDevice):
    """Representation of an Zwave garage door device."""

    def __init__(self, value):
        """Initialize the zwave garage door."""
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)

    @property
    def is_closed(self):
        """Return the current position of Zwave garage door."""
        return not self._value.data

    def close_cover(self):
        """Close the garage door."""
        self._value.data = False

    def open_cover(self):
        """Open the garage door."""
        self._value.data = True
