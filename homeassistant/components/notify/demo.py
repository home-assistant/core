"""
Demo notification service.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.notify import (ATTR_TITLE, ATTR_CAPTION,
                                             BaseNotificationService)

EVENT_NOTIFY_MESSAGE = "notify_message"
EVENT_NOTIFY_PHOTO = "notify_photo"
EVENT_NOTIFY_LOCATION = "notify_location"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the demo for notify platform."""
    add_devices([DemoNotificationService(hass, "Notify")])


# pylint: disable=too-few-public-methods
class DemoNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, hass, name):
        """Initialize the service."""
        self.hass = hass
        self._name = name

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message, **kwargs):
        """Send a message."""
        title = kwargs.get(ATTR_TITLE)
        self.hass.bus.fire(EVENT_NOTIFY_MESSAGE, {"title": title,
                                                  "message": message})

    def send_photo(self, photo, **kwargs):
        """Send a photo."""
        caption = kwargs.get(ATTR_CAPTION)
        self.hass.bus.fire(EVENT_NOTIFY_PHOTO, {"photo": photo,
                                                "caption": caption})

    def send_location(self, latitude, longitude, **kwargs):
        """Send a location."""
        caption = kwargs.get(ATTR_CAPTION)
        self.hass.bus.fire(EVENT_NOTIFY_LOCATION, {"latitude": latitude,
                                                   "longitude": longitude,
                                                   "caption": caption})
