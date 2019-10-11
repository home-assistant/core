"""Support for Unifi Led lights."""
import logging

import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    Light,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default="20443"): cv.string,
        vol.Optional(CONF_ID): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Unifi LED platform."""

    from unifiled import unifiled

    # Assign configuration variables.
    # The configuration check takes care they are present.
    _ip = config[CONF_HOST]
    _port = config[CONF_PORT]
    _username = config[CONF_USERNAME]
    _password = config.get(CONF_PASSWORD)

    api = unifiled(_ip, _port, username=_username, password=_password)

    # Verify that passed in configuration works
    if not api.getloginstate():
        _LOGGER.error("Could not connect to unifiled controller")
        return

    # Add devices
    add_entities(
        UnifiLedLight(light, _ip, _port, _username, _password)
        for light in api.getlights()
    )


class UnifiLedLight(Light):
    """Representation of an unifiled Light."""

    def __init__(self, light, ip, port, username, password):
        """Init Unifi LED Light."""

        from unifiled import unifiled

        self._api = unifiled(ip, port, username=username, password=password)
        self._light = light
        self._name = light["name"]
        self._unique_id = light["id"]
        self._state = light["status"]["output"]
        self._brightness = self._api.convertfrom100to255(light["status"]["led"])
        self._features = SUPPORT_BRIGHTNESS

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness name of this light."""
        return self._brightness

    @property
    def unique_id(self):
        """Return the unique id of this light."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Return the supported features of this light."""
        return self._features

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._api.setdevicebrightness(
            self._unique_id,
            str(self._api.convertfrom255to100(kwargs.get(ATTR_BRIGHTNESS, 255))),
        )
        self._api.setdeviceoutput(self._unique_id, 1)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._api.setdeviceoutput(self._unique_id, 0)

    def update(self):
        """Update the light states."""
        self._state = self._api.getlightstate(self._unique_id)
        self._brightness = self._api.convertfrom100to255(
            self._api.getlightbrightness(self._unique_id)
        )
