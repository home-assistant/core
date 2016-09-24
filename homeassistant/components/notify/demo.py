"""
Demo notification service.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.notify import BaseNotificationService

EVENT_NOTIFY = "notify"


def get_service(hass, config):
    """Get the demo notification service."""
    return DemoNotificationService(hass)


# pylint: disable=too-few-public-methods
class DemoNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, hass):
        """Initialize the service."""
        self.hass = hass

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        return {"test target name": "test target id"}

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        kwargs['message'] = message
        self.hass.bus.fire(EVENT_NOTIFY, kwargs)
