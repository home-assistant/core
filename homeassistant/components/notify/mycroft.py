"""
Mycroft AI notification platform
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.mycroft/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService, ATTR_TITLE)
from homeassistant.const import (CONF_TOKEN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['mycroftapi==0.1.2']

_LOGGER = logging.getLogger(__name__)

mycroft_ip = 'mycroft_ip'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(mycroft_ip): cv.string
})


# pylint: disable=unused-variable
def get_service(hass, config, discovery_info=None):
    """Get the Mycroft notification service."""
    return MycroftNotificationService(
        config.get(mycroft_ip))


class MycroftNotificationService(BaseNotificationService):
    """The Mycroft Notification Service."""

    def __init__(self, mycroft_ip):
        """Initialize the service."""
        self.mycroft_ip = mycroft_ip

    def send_message(self, message="", **kwargs):
        from mycroftapi import MycroftAPI
        """Send a message mycroft to speak"""
        text = message
        mycroft = MycroftAPI(self.mycroft_ip)
        if mycroft is not None:
            mycroft.speak_text(text)
        else:
            _LOGGER.log("Could not reach this instance of mycroft")

