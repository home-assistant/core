"""Support for Avion dimmers."""
import importlib
import logging
import time

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import (
    CONF_API_KEY, CONF_DEVICES, CONF_ID, CONF_NAME, CONF_PASSWORD,
    CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORT_AVION_LED = SUPPORT_BRIGHTNESS

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_ID): cv.positive_int,
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an Avion switch."""
    # pylint: disable=no-member
    avion = importlib.import_module('avion')

    lights = []
    if CONF_USERNAME in config and CONF_PASSWORD in config:
        devices = avion.get_devices(
            config[CONF_USERNAME], config[CONF_PASSWORD])
        for device in devices:
            lights.append(AvionLight(device))

    for address, device_config in config[CONF_DEVICES].items():
        device = avion.Avion(
            mac=address,
            passphrase=device_config[CONF_API_KEY],
            name=device_config.get(CONF_NAME),
            object_id=device_config.get(CONF_ID),
            connect=False)
        lights.append(AvionLight(device))

    add_entities(lights)


class AvionLight(Light):
    """Representation of an Avion light."""

    def __init__(self, device):
        """Initialize the light."""
        self._name = device.name
        self._address = device.mac
        self._brightness = 255
        self._state = False
        self._switch = device

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_AVION_LED

    @property
    def should_poll(self):
        """Don't poll."""
        return False

    @property
    def assumed_state(self):
        """We can't read the actual state, so assume it matches."""
        return True

    def set_state(self, brightness):
        """Set the state of this lamp to the provided brightness."""
        # pylint: disable=no-member
        avion = importlib.import_module('avion')

        # Bluetooth LE is unreliable, and the connection may drop at any
        # time. Make an effort to re-establish the link.
        initial = time.monotonic()
        while True:
            if time.monotonic() - initial >= 10:
                return False
            try:
                self._switch.set_brightness(brightness)
                break
            except avion.AvionException:
                self._switch.connect()
        return True

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None:
            self._brightness = brightness

        self.set_state(self.brightness)
        self._state = True

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self.set_state(0)
        self._state = False
