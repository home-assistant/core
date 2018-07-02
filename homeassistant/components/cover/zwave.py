"""
Support for Z-Wave cover components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.cover import (
    DOMAIN, SUPPORT_OPEN, SUPPORT_CLOSE, ATTR_POSITION)
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
from homeassistant.components.zwave import async_setup_platform  # noqa # pylint: disable=unused-import
from homeassistant.components.zwave import workaround
from homeassistant.components.cover import CoverDevice

_LOGGER = logging.getLogger(__name__)

SUPPORT_GARAGE = SUPPORT_OPEN | SUPPORT_CLOSE


def get_device(hass, values, node_config, **kwargs):
    """Create Z-Wave entity device."""
    invert_buttons = node_config.get(zwave.CONF_INVERT_OPENCLOSE_BUTTONS)
    if (values.primary.command_class ==
            zwave.const.COMMAND_CLASS_SWITCH_MULTILEVEL
            and values.primary.index == 0):
        return ZwaveRollershutter(hass, values, invert_buttons)
    elif (values.primary.command_class ==
          zwave.const.COMMAND_CLASS_SWITCH_BINARY):
        return ZwaveGarageDoorSwitch(values)
    elif (values.primary.command_class ==
          zwave.const.COMMAND_CLASS_BARRIER_OPERATOR):
        return ZwaveGarageDoorBarrier(values)
    return None


class ZwaveRollershutter(zwave.ZWaveDeviceEntity, CoverDevice):
    """Representation of an Z-Wave cover."""

    def __init__(self, hass, values, invert_buttons):
        """Initialize the Z-Wave rollershutter."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._network = hass.data[zwave.const.DATA_NETWORK]
        self._open_id = None
        self._close_id = None
        self._current_position = None
        self._invert_buttons = invert_buttons

        self._workaround = workaround.get_device_mapping(values.primary)
        if self._workaround:
            _LOGGER.debug("Using workaround %s", self._workaround)
        self.update_properties()

    def update_properties(self):
        """Handle data changes for node values."""
        # Position value
        self._current_position = self.values.primary.data

        if self.values.open and self.values.close and \
                self._open_id is None and self._close_id is None:
            if self._invert_buttons:
                self._open_id = self.values.close.value_id
                self._close_id = self.values.open.value_id
            else:
                self._open_id = self.values.open.value_id
                self._close_id = self.values.close.value_id

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is None:
            return None
        if self.current_cover_position > 0:
            return False
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
            return self._current_position

    def open_cover(self, **kwargs):
        """Move the roller shutter up."""
        self._network.manager.pressButton(self._open_id)

    def close_cover(self, **kwargs):
        """Move the roller shutter down."""
        self._network.manager.pressButton(self._close_id)

    def set_cover_position(self, **kwargs):
        """Move the roller shutter to a specific position."""
        self.node.set_dimmer(self.values.primary.value_id,
                             kwargs.get(ATTR_POSITION))

    def stop_cover(self, **kwargs):
        """Stop the roller shutter."""
        self._network.manager.releaseButton(self._open_id)


class ZwaveGarageDoorBase(zwave.ZWaveDeviceEntity, CoverDevice):
    """Base class for a Zwave garage door device."""

    def __init__(self, values):
        """Initialize the zwave garage door."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._state = None
        self.update_properties()

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self.values.primary.data
        _LOGGER.debug("self._state=%s", self._state)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_GARAGE


class ZwaveGarageDoorSwitch(ZwaveGarageDoorBase):
    """Representation of a switch based Zwave garage door device."""

    @property
    def is_closed(self):
        """Return the current position of Zwave garage door."""
        return not self._state

    def close_cover(self, **kwargs):
        """Close the garage door."""
        self.values.primary.data = False

    def open_cover(self, **kwargs):
        """Open the garage door."""
        self.values.primary.data = True


class ZwaveGarageDoorBarrier(ZwaveGarageDoorBase):
    """Representation of a barrier operator Zwave garage door device."""

    @property
    def is_opening(self):
        """Return true if cover is in an opening state."""
        return self._state == "Opening"

    @property
    def is_closing(self):
        """Return true if cover is in a closing state."""
        return self._state == "Closing"

    @property
    def is_closed(self):
        """Return the current position of Zwave garage door."""
        return self._state == "Closed"

    def close_cover(self, **kwargs):
        """Close the garage door."""
        self.values.primary.data = "Closed"

    def open_cover(self, **kwargs):
        """Open the garage door."""
        self.values.primary.data = "Opened"
