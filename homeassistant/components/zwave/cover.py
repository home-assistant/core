"""Support for Z-Wave covers."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverDevice,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    CONF_INVERT_OPENCLOSE_BUTTONS,
    CONF_INVERT_PERCENT,
    CONF_TILT_OPEN_POSITION,
    ZWaveDeviceEntity,
    workaround,
)
from .const import (
    COMMAND_CLASS_BARRIER_OPERATOR,
    COMMAND_CLASS_MANUFACTURER_PROPRIETARY,
    COMMAND_CLASS_SWITCH_BINARY,
    COMMAND_CLASS_SWITCH_MULTILEVEL,
    DATA_NETWORK,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_GARAGE = SUPPORT_OPEN | SUPPORT_CLOSE


def _to_hex_str(id_in_bytes):
    """Convert a two byte value to a hex string.

    Example: 0x1234 --> '0x1234'
    """
    return "0x{:04x}".format(id_in_bytes)


# For some reason node.manufacturer_id is of type string. So we need to convert
# the values.
FIBARO = _to_hex_str(workaround.FIBARO)
FIBARO222_SHUTTERS = [
    _to_hex_str(workaround.FGR222_SHUTTER2),
    _to_hex_str(workaround.FGRM222_SHUTTER2),
]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old method of setting up Z-Wave covers."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Cover from Config Entry."""

    @callback
    def async_add_cover(cover):
        """Add Z-Wave Cover."""
        async_add_entities([cover])

    async_dispatcher_connect(hass, "zwave_new_cover", async_add_cover)


def get_device(hass, values, node_config, **kwargs):
    """Create Z-Wave entity device."""
    invert_buttons = node_config.get(CONF_INVERT_OPENCLOSE_BUTTONS)
    invert_percent = node_config.get(CONF_INVERT_PERCENT)
    if (
        values.primary.command_class == COMMAND_CLASS_SWITCH_MULTILEVEL
        and values.primary.index == 0
    ):
        if (
            values.primary.node.manufacturer_id == FIBARO
            and values.primary.node.product_type in FIBARO222_SHUTTERS
        ):
            return FibaroFGRM222(
                hass,
                values,
                invert_buttons,
                invert_percent,
                node_config.get(CONF_TILT_OPEN_POSITION),
            )
        return ZwaveRollershutter(hass, values, invert_buttons, invert_percent)
    if values.primary.command_class == COMMAND_CLASS_SWITCH_BINARY:
        return ZwaveGarageDoorSwitch(values)
    if values.primary.command_class == COMMAND_CLASS_BARRIER_OPERATOR:
        return ZwaveGarageDoorBarrier(values)
    return None


class ZwaveRollershutter(ZWaveDeviceEntity, CoverDevice):
    """Representation of an Z-Wave cover."""

    def __init__(self, hass, values, invert_buttons, invert_percent):
        """Initialize the Z-Wave rollershutter."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._network = hass.data[DATA_NETWORK]
        self._open_id = None
        self._close_id = None
        self._current_position = None
        self._invert_buttons = invert_buttons
        self._invert_percent = invert_percent

        self._workaround = workaround.get_device_mapping(values.primary)
        if self._workaround:
            _LOGGER.debug("Using workaround %s", self._workaround)
        self.update_properties()

    def update_properties(self):
        """Handle data changes for node values."""
        # Position value
        self._current_position = self.values.primary.data

        if (
            self.values.open
            and self.values.close
            and self._open_id is None
            and self._close_id is None
        ):
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
                return 100 if self._invert_percent else 0
            if self._current_position >= 95:
                return 0 if self._invert_percent else 100
            return (
                100 - self._current_position
                if self._invert_percent
                else self._current_position
            )

    def open_cover(self, **kwargs):
        """Move the roller shutter up."""
        self._network.manager.pressButton(self._open_id)

    def close_cover(self, **kwargs):
        """Move the roller shutter down."""
        self._network.manager.pressButton(self._close_id)

    def set_cover_position(self, **kwargs):
        """Move the roller shutter to a specific position."""
        self.node.set_dimmer(
            self.values.primary.value_id,
            (100 - kwargs.get(ATTR_POSITION))
            if self._invert_percent
            else kwargs.get(ATTR_POSITION),
        )

    def stop_cover(self, **kwargs):
        """Stop the roller shutter."""
        self._network.manager.releaseButton(self._open_id)


class ZwaveGarageDoorBase(ZWaveDeviceEntity, CoverDevice):
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
        return "garage"

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


class FibaroFGRM222(ZwaveRollershutter):
    """Implementation of proprietary features for Fibaro FGR-222 / FGRM-222.

    This adds support for the tilt feature for the ventian blind mode.
    To enable this you need to configure the devices to use the venetian blind
    mode and to enable the proprietary command class:
    * Set "3: Reports type to Blind position reports sent"
        to value "the main controller using Fibaro Command Class"
    * Set "10: Roller Shutter operating modes"
        to  value "2 - Venetian Blind Mode, with positioning"
    """

    def __init__(
        self, hass, values, invert_buttons, invert_percent, open_tilt_position: int
    ):
        """Initialize the FGRM-222."""
        self._value_blinds = None
        self._value_tilt = None
        self._has_tilt_mode = False  # type: bool
        self._open_tilt_position = 50  # type: int
        if open_tilt_position is not None:
            self._open_tilt_position = open_tilt_position
        super().__init__(hass, values, invert_buttons, invert_percent)

    @property
    def current_cover_tilt_position(self) -> int:
        """Get the tilt of the blinds.

        Saturate values <5 and >94 so that it's easier to detect the end
        positions in automations.
        """
        if not self._has_tilt_mode:
            return None
        if self._value_tilt.data <= 5:
            return 0
        if self._value_tilt.data >= 95:
            return 100
        return self._value_tilt.data

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if not self._has_tilt_mode:
            _LOGGER.error("Can't set cover tilt as device is not yet set up.")
        else:
            # Limit the range to [0-99], as this what that the ZWave command
            # accepts.
            tilt_position = max(0, min(99, kwargs.get(ATTR_TILT_POSITION)))
            _LOGGER.debug("setting tilt to %d", tilt_position)
            self._value_tilt.data = tilt_position

    def open_cover_tilt(self, **kwargs):
        """Set slats to horizontal position."""
        self.set_cover_tilt_position(tilt_position=self._open_tilt_position)

    def close_cover_tilt(self, **kwargs):
        """Close the slats."""
        self.set_cover_tilt_position(tilt_position=0)

    def set_cover_position(self, **kwargs):
        """Move the roller shutter to a specific position.

        If the venetian blinds mode is not activated, fall back to
        the behavior of the parent class.
        """
        if not self._has_tilt_mode:
            super().set_cover_position(**kwargs)
        else:
            _LOGGER.debug("Setting cover position to %s", kwargs.get(ATTR_POSITION))
            self._value_blinds.data = kwargs.get(ATTR_POSITION)

    def _configure_values(self):
        """Get the value objects from the node."""
        for value in self.node.get_values(
            class_id=COMMAND_CLASS_MANUFACTURER_PROPRIETARY
        ).values():
            if value is None:
                continue
            if value.index == 0:
                self._value_blinds = value
            elif value.index == 1:
                self._value_tilt = value
            else:
                _LOGGER.warning(
                    "Undefined index %d for this command class", value.index
                )

        if self._value_tilt is not None:
            # We reached here because the user has configured the Fibaro to
            # report using the MANUFACTURER_PROPRIETARY command class. The only
            # reason for the user to configure this way is if tilt support is
            # needed (aka venetian blind mode). Therefore, turn it on.
            #
            # Note: This is safe to do even if the user has accidentally set
            # this configuration parameter, or configuration parameter 10 to
            # something other than venetian blind mode. The controller will just
            # ignore potential tilt settings sent from home assistant in this
            # case.
            self._has_tilt_mode = True
            _LOGGER.info(
                "Zwave node %s is a Fibaro FGR-222/FGRM-222 with tilt support.",
                self.node_id,
            )

    def update_properties(self):
        """React on properties being updated."""
        if not self._has_tilt_mode:
            self._configure_values()
        if self._value_blinds is not None:
            self._current_position = self._value_blinds.data
        else:
            super().update_properties()
