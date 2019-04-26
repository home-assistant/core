"""Demo notification service."""
from homeassistant.components.notify import BaseNotificationService

EVENT_NOTIFY = "notify"


def get_service(hass, config, discovery_info=None):
    """Get the demo notification service."""
    return DemoNotificationService(hass)


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
