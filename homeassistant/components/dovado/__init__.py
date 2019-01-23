"""
Support for Dovado router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/dovado/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.util import Throttle

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT,
    DEVICE_DEFAULT_NAME)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['dovado==0.4.1']

DOMAIN = 'dovado'

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
})

ATTR_PHONE_NUMBER = 'number'
ATTR_MESSAGE = 'message'

SERVICE_SEND_SMS = 'send_sms'
SEND_SMS_SCHEMA = vol.Schema({
    vol.Required(ATTR_PHONE_NUMBER): cv.string,
    vol.Required(ATTR_MESSAGE): cv.string
})

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup(hass, config):
    """Set up the Dovado component."""
    import dovado

    client = dovado.Dovado(
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_HOST),
        config.get(CONF_PORT)
    )

    hass.data[DOMAIN] = DovadoData(client)

    def send_sms(service):
        """Send SMS through the router."""
        number = service.data[ATTR_PHONE_NUMBER]
        message = service.data[ATTR_MESSAGE]
        _LOGGER.debug("message for %s: %s", number, message)
        client.send_sms(number, message)

    hass.services.register(
        DOMAIN, SERVICE_SEND_SMS, send_sms, schema=SEND_SMS_SCHEMA
    )

    return True


class DovadoData:
    """Maintains a connection to the router."""

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
        _LOGGER.info("Updating")
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