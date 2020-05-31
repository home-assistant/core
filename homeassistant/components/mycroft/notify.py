"""Mycroft AI notification platform."""
import logging

from mycroftapi import MycroftAPI

from homeassistant.components.notify import BaseNotificationService

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Mycroft notification service."""
    return MycroftNotificationService(hass.data["mycroft"])


class MycroftNotificationService(BaseNotificationService):
    """The Mycroft Notification Service."""

    def __init__(self, mycroft_ip):
        """Initialize the service."""
        self.mycroft_ip = mycroft_ip

    def send_message(self, message="", **kwargs):
        """Send a message mycroft to speak on instance."""

        text = message
        mycroft = MycroftAPI(self.mycroft_ip)
        if mycroft is not None:
            mycroft.speak_text(text)
        else:
            _LOGGER.log("Could not reach this instance of mycroft")
