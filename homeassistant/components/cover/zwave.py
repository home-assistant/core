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
from homeassistant.components.zwave import async_setup_platform  # noqa # pylint: disable=unused-import
from homeassistant.components.zwave import workaround
from homeassistant.components.cover import CoverDevice

_LOGGER = logging.getLogger(__name__)

SUPPORT_GARAGE = SUPPORT_OPEN | SUPPORT_CLOSE


def get_device(value, **kwargs):
    """Create zwave entity device."""
    if (value.command_class == zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL
            and value.index == 0):
        return ZwaveRollershutter(value)
    elif (value.command_class == zwave.const.COMMAND_CLASS_SWITCH_BINARY or
          value.command_class == zwave.const.COMMAND_CLASS_BARRIER_OPERATOR):
        return ZwaveGarageDoor(value)
    return None


class ZwaveRollershutter(zwave.ZWaveDeviceEntity, CoverDevice):
    """Representation of an Zwave roller shutter."""

    def __init__(self, value):
        """Initialize the zwave rollershutter."""
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        # pylint: disable=no-member
        self._node = value.node
        self._open_id = None
        self._close_id = None
        self._current_position_id = None
        self._current_position = None

        self._workaround = workaround.get_device_mapping(value)
        if self._workaround:
            _LOGGER.debug("Using workaround %s", self._workaround)
        self.update_properties()

    @property
    def dependent_value_ids(self):
        """List of value IDs a device depends on."""
        if not self._node.is_ready:
            return None
        return [self._current_position_id]

    def update_properties(self):
        """Callback on data changes for node values."""
        # Position value
        if not self._node.is_ready:
            if self._current_position_id is None:
                self._current_position_id = self.get_value(
                    class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL,
                    label=['Level'], member='value_id')
            if self._open_id is None:
                self._open_id = self.get_value(
                    class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL,
                    label=['Open', 'Up'], member='value_id')
            if self._close_id is None:
                self._close_id = self.get_value(
                    class_id=zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL,
                    label=['Close', 'Down'], member='value_id')
        if self._open_id and self._close_id and \
                self._workaround == workaround.WORKAROUND_REVERSE_OPEN_CLOSE:
            self._open_id, self._close_id = self._close_id, self._open_id
            self._workaround = None
        self._current_position = self._node.get_dimmer_level(
            self._current_position_id)

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
