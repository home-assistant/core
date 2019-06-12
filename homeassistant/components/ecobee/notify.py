"""Support for Ecobee Send Message service."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import ecobee
from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

CONF_INDEX = 'index'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_INDEX, default=0): cv.positive_int,
})


def get_service(hass, config, discovery_info=None):
    """Get the Ecobee notification service."""
    index = config.get(CONF_INDEX)
    return EcobeeNotificationService(index)


class EcobeeNotificationService(BaseNotificationService):
    """Implement the notification service for the Ecobee thermostat."""

    def __init__(self, thermostat_index):
        """Initialize the service."""
        self.thermostat_index = thermostat_index

    def send_message(self, message="", **kwargs):
        """Send a message to a command line."""
        ecobee.NETWORK.ecobee.send_message(self.thermostat_index, message)
