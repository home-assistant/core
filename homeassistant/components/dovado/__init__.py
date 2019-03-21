"""Support for Dovado router."""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT,
    DEVICE_DEFAULT_NAME)
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['dovado==0.4.1']

DOMAIN = 'dovado'

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
})

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup(hass, config):
    """Set up the Dovado component."""
    import dovado

    hass.data[DOMAIN] = DovadoData(
        dovado.Dovado(
            config[CONF_USERNAME], config[CONF_PASSWORD],
            config.get(CONF_HOST), config.get(CONF_PORT))
    )
    return True


class DovadoData:
    """Maintain a connection to the router."""

    def __init__(self, client):
        """Set up a new Dovado connection."""
        self._client = client
        self.state = {}

    @property
    def name(self):
        """Name of the router."""
        return self.state.get("product name", DEVICE_DEFAULT_NAME)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update device state."""
        try:
            self.state = self._client.state or {}
            if not self.state:
                return False
            self.state.update(
                connected=self.state.get("modem status") == "CONNECTED")
            _LOGGER.debug("Received: %s", self.state)
            return True
        except OSError as error:
            _LOGGER.warning("Could not contact the router: %s", error)

    @property
    def client(self):
        """Dovado client instance."""
        return self._client
