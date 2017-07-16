"""
Support KNX Lighting actuators.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/Light.knx/
"""
import logging
import voluptuous as vol

from homeassistant.components.knx import (KNXConfig, KNXMultiAddressDevice)
from homeassistant.components.light import (Light, PLATFORM_SCHEMA,
                                            SUPPORT_BRIGHTNESS,
                                            ATTR_BRIGHTNESS)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_STATE_ADDRESS = 'state_address'
CONF_BRIGHTNESS_ADDRESS = 'brightness_address'
CONF_BRIGHTNESS_STATE_ADDRESS = 'brightness_state_address'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'KNX Light'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the KNX light platform."""
    add_devices([KNXLight(hass, KNXConfig(config))])


class KNXLight(KNXMultiAddressDevice, Light):
    """Representation of a KNX Light device."""

    def __init__(self, hass, config):
        """Initialize the cover."""
        KNXMultiAddressDevice.__init__(
            self, hass, config,
            [],  # required
            optional=['state', 'brightness', 'brightness_state']
        )
        self._hass = hass
        self._supported_features = 0

        if CONF_BRIGHTNESS_ADDRESS in config.config:
            _LOGGER.debug("%s is dimmable", self.name)
            self._supported_features = self._supported_features | \
                SUPPORT_BRIGHTNESS
            self._brightness = None

    def turn_on(self, **kwargs):
        """Turn the switch on.

        This sends a value 1 to the group address of the device
        """
        _LOGGER.debug("%s: turn on", self.name)
        self.set_value('base', [1])
        self._state = 1

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            _LOGGER.debug("turn_on requested brightness for light: %s is: %s ",
                          self.name, self._brightness)
            assert self._brightness <= 255
            self.set_value("brightness", [self._brightness])

        if not self.should_poll:
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off.

        This sends a value 1 to the group address of the device
        """
        _LOGGER.debug("%s: turn off", self.name)
        self.set_value('base', [0])
        self._state = 0
        if not self.should_poll:
            self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return True if the value is not 0 is on, else False."""
        return self._state != 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def update(self):
        """Update device state."""
        super().update()
        if self.has_attribute('brightness_state'):
            value = self.value('brightness_state')
            if value is not None:
                self._brightness = int.from_bytes(value, byteorder='little')
                _LOGGER.debug("%s: brightness = %d",
                              self.name, self._brightness)

        if self.has_attribute('state'):
            self._state = self.value("state")[0]
            _LOGGER.debug("%s: state = %d", self.name, self._state)

    def should_poll(self):
        """No polling needed for a KNX light."""
        return False
