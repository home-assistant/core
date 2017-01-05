"""
Lannouncer platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.lannouncer/
"""
import logging

from urllib.parse import quote_plus
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, ATTR_DATA, BaseNotificationService)
from homeassistant.const import (CONF_HOST, CONF_PORT)
import homeassistant.helpers.config_validation as cv

ATTR_METHOD = 'method'
ATTR_METHOD_SPEAK = 'speak'
ATTR_METHOD_ALARM = 'alarm'

DEFAULT_PORT = 1035

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the Lannouncer notification service."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    return LannouncerNotificationService(host, port)


class LannouncerNotificationService(BaseNotificationService):
    """Implementation of a notification service for Lannouncer."""

    def __init__(self, host, port):
        """Initialize the service."""
        self._host = host
        self._port = port

    def send_message(self, message="", **kwargs):
        """Send a message to Lannouncer."""
        data = kwargs.get(ATTR_DATA)
        if data is not None and ATTR_METHOD in data:
            method = data.get(ATTR_METHOD)
        else:
            method = ATTR_METHOD_SPEAK

        if method == ATTR_METHOD_SPEAK:
            url = "http://{}:{}/?SPEAK={}&@DONE@".format(
                self._host, self._port, quote_plus(message))

        elif method == ATTR_METHOD_ALARM:
            url = "http://{}:{}/?ALARM={}&@DONE@".format(
                self._host, self._port, quote_plus(message))

        else:
            _LOGGER.error("Unknown method %s", method)
            return None

        try:
            _LOGGER.debug("Sending message to %s", url)
            requests.get(url)

        except requests.ConnectionError:
            # Lannouncer doesn't send a HTTP response code,
            # but just prints the raw string LANnouncer: OK
            pass

        except requests.exceptions.RequestException as err:
            _LOGGER.exception('Could not send lannouncer notification: %s',
                              err)
