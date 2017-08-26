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

REQUIREMENTS = ['websocket-client']

_LOGGER = logging.getLogger(__name__)

IP = 'mycroft_ip'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(IP): cv.string
})


# pylint: disable=unused-variable
def get_service(hass, config, discovery_info=None):
    """Get the Mycroft notification service."""
    return MycroftNotificationService(
        config.get(IP))


class MycroftNotificationService(BaseNotificationService):
    """The Mycroft Notification Service."""

    def __init__(self, ip):
        """Initialize the service."""
        self._ip = ip

    def send_message(self, message="", **kwargs):
        from websocket import create_connection
        import ssl
        """Send a message mycroft to speak"""
        text = message
        _LOGGER.info("The text we are sending to mycroft is: {}".format(text))
        ws = create_connection("ws://10.0.0.7:8181/core", sslopt={"cert_reqs": ssl.CERT_NONE})
        mycroft_speak = ('"{}"'.format(text))
        mycroft_type = '"speak"'
        mycroft_data = '{"expect_response": false, "utterance": %s}, "context": null' % mycroft_speak
        message = '{"type": ' + mycroft_type + ', "data": ' + mycroft_data + '}'
        try:
            ws.send(message)
        except:
            _LOGGER("We hit an error trying to send to mycroft.")
