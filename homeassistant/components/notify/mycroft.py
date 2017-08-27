"""
Mycroft AI notification platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.mycroft/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import BaseNotificationService


REQUIREMENTS = ['mycroftapi==0.1.2']

_LOGGER = logging.getLogger(__name__)


class MycroftNotificationService(BaseNotificationService):
    """The Mycroft Notification Service."""

    def __init__(self, mycroft_ip):
        """Initialize the service."""
        self.mycroft_ip = mycroft_ip

    def send_message(self, message="", **kwargs):
        from mycroftapi import MycroftAPI
        """Send a message mycroft to speak on instance"""
        text = message
        mycroft = MycroftAPI(self.mycroft_ip)
        if mycroft is not None:
            mycroft.speak_text(text)
        else:
            _LOGGER.log("Could not reach this instance of mycroft")

     return MycroftNotificationService(hass.data['mycroft'])
