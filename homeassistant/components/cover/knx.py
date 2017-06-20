"""
Support for KNX covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.knx/
"""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    CoverDevice, PLATFORM_SCHEMA, ATTR_POSITION, DEVICE_CLASSES_SCHEMA
)
from homeassistant.components.knx import (KNXConfig, KNXMultiAddressDevice)
from homeassistant.const import (CONF_NAME, CONF_DEVICE_CLASS)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_GETPOSITION_ADDRESS = 'getposition_address'
CONF_SETPOSITION_ADDRESS = 'setposition_address'
CONF_STOP = 'stop_address'
CONF_UPDOWN = 'updown_address'

DEFAULT_NAME = 'KNX Cover'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_UPDOWN): cv.string,
    vol.Required(CONF_STOP): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_GETPOSITION_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SETPOSITION_ADDRESS): cv.string,
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
            optional=['setposition', 'getposition']
        )
        self._device_class = config.config.get(CONF_DEVICE_CLASS)
        self._hass = hass
        self._current_pos = None
        self._target_pos = None

    @property
    def should_poll(self):
        """Polling is needed for the KNX cover."""
        return True

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

    def set_cover_position(self, **kwargs):
        """Set new target position."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return

        self._target_pos = position
        self.set_percentage('setposition', position)
        _LOGGER.debug("%s: Set target position to %d", self.name, position)

    def update(self):
        """Update device state."""
        super().update()
        value = self.get_percentage('getposition')
        if value is not None:
            self._current_pos = value
            _LOGGER.debug("%s: position = %d", self.name, value)

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

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class
