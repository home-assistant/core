"""
LG WebOS TV notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.webostv/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (BaseNotificationService,
                                             PLATFORM_SCHEMA)
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['https://github.com/TheRealLink/pylgtv'
                '/archive/v0.1.2.zip'
                '#pylgtv==0.1.2']


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})


def get_service(hass, config):
    """Return the notify service."""
    from pylgtv import WebOsClient
    from pylgtv import PyLGTVPairException

    client = WebOsClient(config.get(CONF_HOST))

    try:
        client.register()
    except PyLGTVPairException:
        _LOGGER.error('Pairing failed.')
        return None
    except OSError:
        _LOGGER.error('Host unreachable.')
        return None

    return LgWebOSNotificationService(client)


# pylint: disable=too-few-public-methods
class LgWebOSNotificationService(BaseNotificationService):
    """Implement the notification service for LG WebOS TV."""

    def __init__(self, client):
        """Initialize the service."""
        self._client = client

    def send_message(self, message="", **kwargs):
        """Send a message to the tv."""
        from pylgtv import PyLGTVPairException

        try:
            self._client.send_message(message)
        except PyLGTVPairException:
            _LOGGER.error('Pairing failed.')
        except OSError:
            _LOGGER.error('Host unreachable.')
