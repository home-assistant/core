"""Support for Ecobee Send Message service."""
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
import homeassistant.helpers.config_validation as cv

from .const import CONF_INDEX, DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_INDEX, default=0): cv.positive_int}
)


def get_service(hass, config, discovery_info=None):
    """Get the Ecobee notification service."""
    index = config.get(CONF_INDEX)
    return EcobeeNotificationService(hass, index)


class EcobeeNotificationService(BaseNotificationService):
    """Implement the notification service for the Ecobee thermostat."""

    def __init__(self, hass, thermostat_index):
        """Initialize the service."""
        self.hass = hass
        self.thermostat_index = thermostat_index

    def send_message(self, message="", **kwargs):
        """Send a message."""
        data = self.hass.data[DOMAIN]
        data.ecobee.send_message(self.thermostat_index, message)
