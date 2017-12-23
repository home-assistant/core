"""
Support for Greenwave Reality (TCP Connected) lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.greenwave/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, Light, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

SUPPORTED_FEATURES = (SUPPORT_BRIGHTNESS)

REQUIREMENTS = ['greenwavereality==0.2.9']
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required("version"): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Greenwave Reality Platform."""
    import greenwavereality as greenwave
    import os
    host = config.get(CONF_HOST)
    tokenfile = hass.config.path('.greenwave')
    if config.get("version") == 3:
        if os.path.exists(tokenfile):
            tokenfile = open(tokenfile)
            token = tokenfile.read()
            tokenfile.close()
        else:
            token = greenwave.grab_token(host, 'hass', 'homeassistant')
            tokenfile = open(tokenfile, "w+")
            tokenfile.write(token)
            tokenfile.close()
    else:
        token = None
    doc = greenwave.grab_xml(host, token)
    add_devices(GreenwaveLight(device, host, token) for device in doc)


class GreenwaveLight(Light):
    """Representation of an Greenwave Reality Light."""

    def __init__(self, light, host, token):
        """Initialize a Greenwave Reality Light."""
        import greenwavereality as greenwave
        self._did = light['did']
        self._name = light['name']
        self._state = int(light['state'])
        self._brightness = greenwave.hass_brightness(light)
        self._host = host
        self._online = greenwave.check_online(light)
        self.token = token

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def available(self):
        """Return True if entity is available."""
        return self._online

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        import greenwavereality as greenwave
        temp_brightness = int((kwargs.get(ATTR_BRIGHTNESS, 255)
                               / 255) * 100)
        greenwave.set_brightness(self._host, self._did,
                                 temp_brightness, self.token)
        greenwave.turn_on(self._host, self._did, self.token)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        import greenwavereality as greenwave
        greenwave.turn_off(self._host, self._did, self.token)

    def update(self):
        """Fetch new state data for this light."""
        import greenwavereality as greenwave
        doc = greenwave.grab_xml(self._host, self.token)

        for device in doc:
            if device['did'] == self._did:
                self._state = int(device['state'])
                self._brightness = greenwave.hass_brightness(device)
                self._online = greenwave.check_online(device)
                self._name = device['name']
