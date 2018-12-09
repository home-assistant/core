"""
Support for setting the Transmission BitTorrent client Turtle Mode.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.transmission/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_PASSWORD, CONF_USERNAME, STATE_OFF,
    STATE_ON)
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['transmissionrpc==0.11']

_LOGGING = logging.getLogger(__name__)

DEFAULT_NAME = 'Transmission Turtle Mode'
DEFAULT_PORT = 9091

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Transmission switch."""
    import transmissionrpc
    from transmissionrpc.error import TransmissionError

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    port = config.get(CONF_PORT)

    try:
        transmission_api = transmissionrpc.Client(
            host, port=port, user=username, password=password)
        transmission_api.session_stats()
    except TransmissionError as error:
        _LOGGING.error(
            "Connection to Transmission API failed on %s:%s with message %s",
            host, port, error.original
        )
        return False

    add_entities([TransmissionSwitch(transmission_api, name)])


class TransmissionSwitch(ToggleEntity):
    """Representation of a Transmission switch."""

    def __init__(self, transmission_client, name):
        """Initialize the Transmission switch."""
        self._name = name
        self.transmission_client = transmission_client
        self._state = STATE_OFF

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):
        """Poll for status regularly."""
        return True

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGING.debug("Turning Turtle Mode of Transmission on")
        self.transmission_client.set_session(alt_speed_enabled=True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGING.debug("Turning Turtle Mode of Transmission off")
        self.transmission_client.set_session(alt_speed_enabled=False)

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        active = self.transmission_client.get_session().alt_speed_enabled
        self._state = STATE_ON if active else STATE_OFF
