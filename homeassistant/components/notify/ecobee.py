"""
Support for ecobee Send Message service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.ecobee/
"""
import logging
from homeassistant.const import CONF_NAME
from homeassistant.components import ecobee
from homeassistant.components.notify import BaseNotificationService

DEPENDENCIES = ['ecobee']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the Ecobee notification service."""
    index = int(config['index']) if 'index' in config else 0
    add_devices([EcobeeNotificationService(index, config.get(CONF_NAME))])


# pylint: disable=too-few-public-methods,abstract-method
class EcobeeNotificationService(BaseNotificationService):
    """Implement the notification service for the Ecobee thermostat."""

    def __init__(self, thermostat_index, name):
        """Initialize the service."""
        self.thermostat_index = thermostat_index
        self._name = name

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message, **kwargs):
        """Send a message to a command line."""
        ecobee.NETWORK.ecobee.send_message(self.thermostat_index, message)
