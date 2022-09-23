"""Support for Ecobee Send Message service."""

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService

from homeassistant.exceptions import RequiredParameterMissing

from .const import DOMAIN


def get_service(hass, config, discovery_info=None):
    """Get the Ecobee notification service."""
    if discovery_info is None:
        return None

    data = hass.data[DOMAIN]
    return EcobeeNotificationService(data.ecobee)


class EcobeeNotificationService(BaseNotificationService):
    """Implement the notification service for the Ecobee thermostat."""

    def __init__(self, ecobee):
        """Initialize the service."""
        self.ecobee = ecobee

    def send_message(self, message="", **kwargs):
        """Send a message."""
        targets = kwargs.get(ATTR_TARGET, None)

        if not targets:
            raise RequiredParameterMissing(["target"])

        for target in targets:
            thermostat_index = int(target)
            self.ecobee.send_message(thermostat_index, message)
