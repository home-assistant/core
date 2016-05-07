"""
LG WebOS TV notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.webostv/
"""
import logging

from homeassistant.components.notify import (BaseNotificationService, DOMAIN)
from homeassistant.const import (CONF_HOST, CONF_NAME)
from homeassistant.helpers import validate_config

REQUIREMENTS = ['https://github.com/TheRealLink/pylgtv'
                '/archive/v0.1.2.zip'
                '#pylgtv==0.1.2']

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Return the notify service."""
    if not validate_config({DOMAIN: config}, {DOMAIN: [CONF_HOST, CONF_NAME]},
                           _LOGGER):
        return None

    host = config.get(CONF_HOST, None)

    if not host:
        _LOGGER.error('No host provided.')
        return None

    from pylgtv import WebOsClient
    from pylgtv import PyLGTVPairException

    client = WebOsClient(host)

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
