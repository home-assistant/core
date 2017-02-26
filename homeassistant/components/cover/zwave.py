"""
Support for Zwave cover components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.cover import (
    DOMAIN, SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
from homeassistant.components.zwave import workaround
from homeassistant.components.cover import CoverDevice

_LOGGER = logging.getLogger(__name__)

SUPPORT_GARAGE = SUPPORT_OPEN | SUPPORT_CLOSE


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

        self._workaround = workaround.get_device_mapping(value)
        if self._workaround:
            _LOGGER.debug("Using workaround %s", self._workaround)
        self.update_properties()

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
        if self._workaround == workaround.WORKAROUND_REVERSE_OPEN_CLOSE:
            self._open_id, self._close_id = self._close_id, self._open_id

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
        if self._workaround == workaround.WORKAROUND_NO_POSITION:
            return None
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
        self.update_properties()

    def update_properties(self):
        """Callback on data changes for node values."""
        self._state = self._value.data

    @property
    def is_closed(self):
        """Return the current position of Zwave garage door."""
        return not self._state

    def close_cover(self):
        """Close the garage door."""
        self._value.data = False

    def open_cover(self):
        """Open the garage door."""
        self._value.data = True

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_GARAGE
