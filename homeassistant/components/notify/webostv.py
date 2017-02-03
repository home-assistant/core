"""
LG WebOS TV notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.webostv/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_FILENAME, CONF_HOST)

REQUIREMENTS = ['https://github.com/TheRealLink/pylgtv/archive/v0.1.3.zip'
                '#pylgtv==0.1.3']

_LOGGER = logging.getLogger(__name__)

WEBOSTV_CONFIG_FILE = 'webostv.conf'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_FILENAME, default=WEBOSTV_CONFIG_FILE): cv.string
})


def get_service(hass, config, discovery_info=None):
    """Return the notify service."""
    from pylgtv import WebOsClient
    from pylgtv import PyLGTVPairException

    path = hass.config.path(config.get(CONF_FILENAME))
    client = WebOsClient(config.get(CONF_HOST), key_file_path=path)

    try:
        client.register()
    except PyLGTVPairException:
        _LOGGER.error("Pairing with TV failed")
        return None
    except OSError:
        _LOGGER.error("TV unreachable")
        return None

    return LgWebOSNotificationService(client)


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
            _LOGGER.error("Pairing with TV failed")
        except OSError:
            _LOGGER.error("TV unreachable")
