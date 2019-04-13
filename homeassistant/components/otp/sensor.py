"""Support for One-Time Password (OTP)."""
import time
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_TOKEN)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'OTP Sensor'

TIME_STEP = 30  # Default time step assumed by Google Authenticator

ICON = 'mdi:update'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the OTP sensor."""
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    async_add_entities([TOTPSensor(name, token)], True)
    return True


# Only TOTP supported at the moment, HOTP might be added later
class TOTPSensor(Entity):
    """Representation of a TOTP sensor."""

    def __init__(self, name, token):
        """Initialize the sensor."""
        import pyotp
        self._name = name
        self._otp = pyotp.TOTP(token)
        self._state = None
        self._next_expiration = None

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._call_loop()

    @callback
    def _call_loop(self):
        self._state = self._otp.now()
        self.async_schedule_update_ha_state()

        # Update must occur at even TIME_STEP, e.g. 12:00:00, 12:00:30,
        # 12:01:00, etc. in order to have synced time (see RFC6238)
        self._next_expiration = TIME_STEP - (time.time() % TIME_STEP)
        self.hass.loop.call_later(self._next_expiration, self._call_loop)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
