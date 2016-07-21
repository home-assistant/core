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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Return the notify service."""
    if not validate_config({DOMAIN: config}, {DOMAIN: [CONF_HOST, CONF_NAME]},
                           _LOGGER):
        return False

    host = config.get(CONF_HOST, None)
    name = config.get(CONF_NAME)

    if not host:
        _LOGGER.error('No host provided.')
        return False

    from pylgtv import WebOsClient
    from pylgtv import PyLGTVPairException

    client = WebOsClient(host)

    try:
        client.register()
    except PyLGTVPairException:
        _LOGGER.error('Pairing failed.')
        return False
    except OSError:
        _LOGGER.error('Host unreachable.')
        return False

    add_devices([LgWebOSNotificationService(client, name)])


# pylint: disable=too-few-public-methods,abstract-method
class LgWebOSNotificationService(BaseNotificationService):
    """Implement the notification service for LG WebOS TV."""

    def __init__(self, client, name):
        """Initialize the service."""
        self._client = client
        self._name = name

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message, **kwargs):
        """Send a message to the tv."""
        from pylgtv import PyLGTVPairException

        try:
            self._client.send_message(message)
        except PyLGTVPairException:
            _LOGGER.error('Pairing failed.')
        except OSError:
            _LOGGER.error('Host unreachable.')
