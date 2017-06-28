"""
Support for KNX covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.knx/
"""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    CoverDevice, PLATFORM_SCHEMA, ATTR_POSITION, DEVICE_CLASSES_SCHEMA,
    SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_SET_POSITION, SUPPORT_STOP,
    SUPPORT_SET_TILT_POSITION
)
from homeassistant.components.knx import (KNXConfig, KNXMultiAddressDevice)
from homeassistant.const import (CONF_NAME, CONF_DEVICE_CLASS)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_GETPOSITION_ADDRESS = 'getposition_address'
CONF_SETPOSITION_ADDRESS = 'setposition_address'
CONF_GETANGLE_ADDRESS = 'getangle_address'
CONF_SETANGLE_ADDRESS = 'setangle_address'
CONF_STOP = 'stop_address'
CONF_UPDOWN = 'updown_address'
CONF_INVERT_POSITION = 'invert_position'
CONF_INVERT_ANGLE = 'invert_angle'

DEFAULT_NAME = 'KNX Cover'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_UPDOWN): cv.string,
    vol.Required(CONF_STOP): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_GETPOSITION_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SETPOSITION_ADDRESS): cv.string,
    vol.Optional(CONF_INVERT_POSITION, default=False): cv.boolean,
    vol.Inclusive(CONF_GETANGLE_ADDRESS, 'angle'): cv.string,
    vol.Inclusive(CONF_SETANGLE_ADDRESS, 'angle'): cv.string,
    vol.Optional(CONF_INVERT_ANGLE, default=False): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_devices([KNXCover(hass, KNXConfig(config))])


class KNXCover(KNXMultiAddressDevice, CoverDevice):
    """Representation of a KNX cover. e.g. a rollershutter."""

    def __init__(self, hass, config):
        """Initialize the cover."""
        KNXMultiAddressDevice.__init__(
            self, hass, config,
            ['updown', 'stop'],  # required
            optional=['setposition', 'getposition',
                      'getangle', 'setangle']
        )
        self._device_class = config.config.get(CONF_DEVICE_CLASS)
        self._invert_position = config.config.get(CONF_INVERT_POSITION)
        self._invert_angle = config.config.get(CONF_INVERT_ANGLE)
        self._hass = hass
        self._current_pos = None
        self._target_pos = None
        self._current_tilt = None
        self._target_tilt = None
        self._supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | \
            SUPPORT_SET_POSITION | SUPPORT_STOP

        # Tilt is only supported, if there is a angle get and set address
        if CONF_SETANGLE_ADDRESS in config.config:
            _LOGGER.debug("%s: Tilt supported at addresses %s, %s",
                          self.name, config.config.get(CONF_SETANGLE_ADDRESS),
                          config.config.get(CONF_GETANGLE_ADDRESS))
            self._supported_features = self._supported_features | \
                SUPPORT_SET_TILT_POSITION

    @property
    def should_poll(self):
        """Polling is needed for the KNX cover."""
        return True

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            if self.current_cover_position > 0:
                return False
            else:
                return True

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._current_pos

    @property
    def target_position(self):
        """Return the position we are trying to reach: 0 - 100."""
        return self._target_pos

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._current_tilt

    @property
    def target_tilt(self):
        """Return the tilt angle (in %) we are trying to reach: 0 - 100."""
        return self._target_tilt

    def set_cover_position(self, **kwargs):
        """Set new target position."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return

        if self._invert_position:
            position = 100-position

        self._target_pos = position
        self.set_percentage('setposition', position)
        _LOGGER.debug("%s: Set target position to %d", self.name, position)

    def update(self):
        """Update device state."""
        super().update()
        value = self.get_percentage('getposition')
        if value is not None:
            self._current_pos = value
            if self._invert_position:
                self._current_pos = 100-value
            _LOGGER.debug("%s: position = %d", self.name, value)

        if self._supported_features & SUPPORT_SET_TILT_POSITION:
            value = self.get_percentage('getangle')
            if value is not None:
                self._current_tilt = value
                if self._invert_angle:
                    self._current_tilt = 100-value
                _LOGGER.debug("%s: tilt = %d", self.name, value)

    def open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.debug("%s: open: updown = 0", self.name)
        self.set_int_value('updown', 0)

    def close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.debug("%s: open: updown = 1", self.name)
        self.set_int_value('updown', 1)

    def stop_cover(self, **kwargs):
        """Stop the cover movement."""
        _LOGGER.debug("%s: stop: stop = 1", self.name)
        self.set_int_value('stop', 1)

    def set_cover_tilt_position(self, tilt_position, **kwargs):
        """Move the cover til to a specific position."""
        if self._invert_angle:
            tilt_position = 100-tilt_position

        self._target_tilt = round(tilt_position, -1)
        self.set_percentage('setangle', tilt_position)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class
