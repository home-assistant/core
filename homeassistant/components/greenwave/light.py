"""Support for Greenwave Reality (TCP Connected) lights."""
from datetime import timedelta
import logging
import os

import greenwavereality as greenwave
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_VERSION = "version"

SUPPORTED_FEATURES = SUPPORT_BRIGHTNESS

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_VERSION): cv.positive_int}
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Greenwave Reality Platform."""
    host = config.get(CONF_HOST)
    tokenfile = hass.config.path(".greenwave")
    if config.get(CONF_VERSION) == 3:
        if os.path.exists(tokenfile):
            with open(tokenfile, encoding="utf8") as tokenfile:
                token = tokenfile.read()
        else:
            try:
                token = greenwave.grab_token(host, "hass", "homeassistant")
            except PermissionError:
                _LOGGER.error("The Gateway Is Not In Sync Mode")
                raise
            with open(tokenfile, "w+", encoding="utf8") as tokenfile:
                tokenfile.write(token)
    else:
        token = None
    bulbs = greenwave.grab_bulbs(host, token)
    add_entities(
        GreenwaveLight(device, host, token, GatewayData(host, token))
        for device in bulbs.values()
    )


class GreenwaveLight(LightEntity):
    """Representation of an Greenwave Reality Light."""

    def __init__(self, light, host, token, gatewaydata):
        """Initialize a Greenwave Reality Light."""
        self._did = int(light["did"])
        self._name = light["name"]
        self._state = int(light["state"])
        self._brightness = greenwave.hass_brightness(light)
        self._host = host
        self._online = greenwave.check_online(light)
        self._token = token
        self._gatewaydata = gatewaydata

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
        temp_brightness = int((kwargs.get(ATTR_BRIGHTNESS, 255) / 255) * 100)
        greenwave.set_brightness(self._host, self._did, temp_brightness, self._token)
        greenwave.turn_on(self._host, self._did, self._token)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        greenwave.turn_off(self._host, self._did, self._token)

    def update(self):
        """Fetch new state data for this light."""
        self._gatewaydata.update()
        bulbs = self._gatewaydata.greenwave

        self._state = int(bulbs[self._did]["state"])
        self._brightness = greenwave.hass_brightness(bulbs[self._did])
        self._online = greenwave.check_online(bulbs[self._did])
        self._name = bulbs[self._did]["name"]


class GatewayData:
    """Handle Gateway data and limit updates."""

    def __init__(self, host, token):
        """Initialize the data object."""
        self._host = host
        self._token = token
        self._greenwave = greenwave.grab_bulbs(host, token)

    @property
    def greenwave(self):
        """Return Gateway API object."""
        return self._greenwave

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the gateway."""
        self._greenwave = greenwave.grab_bulbs(self._host, self._token)
        return self._greenwave
