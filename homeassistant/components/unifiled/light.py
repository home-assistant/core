"""Support for Unifi Led lights."""
import logging

from unifiled import unifiled
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=20443): vol.All(cv.port, cv.string),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Unifi LED platform."""

    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    api = unifiled(host, port, username=username, password=password)

    # Verify that passed in configuration works
    if not api.getloginstate():
        _LOGGER.error("Could not connect to unifiled controller")
        return

    add_entities(UnifiLedLight(light, api) for light in api.getlights())


class UnifiLedLight(LightEntity):
    """Representation of an unifiled Light."""

    def __init__(self, light, api):
        """Init Unifi LED Light."""

        self._api = api
        self._light = light
        self._name = light["name"]
        self._unique_id = light["id"]
        self._state = light["status"]["output"]
        self._available = light["isOnline"]
        self._brightness = self._api.convertfrom100to255(light["status"]["led"])
        self._features = SUPPORT_BRIGHTNESS

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def available(self):
        """Return the available state of this light."""
        return self._available

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
        self._available = self._api.getlightavailable(self._unique_id)
