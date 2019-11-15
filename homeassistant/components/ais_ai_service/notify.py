"""AIS notification service."""
from homeassistant.components.notify import BaseNotificationService


def get_service(hass, config, discovery_info=None):
    """Get the AIS notification service."""
    return AisNotificationService(hass)


class AisNotificationService(BaseNotificationService):
    """Implement AIS notification service."""

    def __init__(self, hass):
        """Initialize the service."""
        self.hass = hass

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        return {"AIS target name": "AIS target id"}

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        kwargs["message"] = message
        self.hass.services.call("ais_ai_service", "say_it", {"text": message})
