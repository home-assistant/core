"""
Support for ecobee Send Message service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.ecobee/
"""
import logging
from homeassistant.components import ecobee
from homeassistant.components.notify import BaseNotificationService

DEPENDENCIES = ['ecobee']
_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the Ecobee notification service."""
    index = int(config['index']) if 'index' in config else 0
    return EcobeeNotificationService(index)


# pylint: disable=too-few-public-methods
class EcobeeNotificationService(BaseNotificationService):
    """Implement the notification service for the Ecobee thermostat."""

    def __init__(self, thermostat_index):
        """Initialize the service."""
        self.thermostat_index = thermostat_index

    def send_message(self, message="", **kwargs):
        """Send a message to a command line."""
        ecobee.NETWORK.ecobee.send_message(self.thermostat_index, message)
