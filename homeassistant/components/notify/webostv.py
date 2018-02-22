"""
LG WebOS TV notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.webostv/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_DATA, BaseNotificationService, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_FILENAME, CONF_HOST, CONF_ICON)

REQUIREMENTS = ['pylgtv==0.1.7']

_LOGGER = logging.getLogger(__name__)

WEBOSTV_CONFIG_FILE = 'webostv.conf'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_FILENAME, default=WEBOSTV_CONFIG_FILE): cv.string,
    vol.Optional(CONF_ICON): cv.string
})


def get_service(hass, config, discovery_info=None):
    """Return the notify service."""
    from pylgtv import WebOsClient
    from pylgtv import PyLGTVPairException

    path = hass.config.path(config.get(CONF_FILENAME))
    client = WebOsClient(config.get(CONF_HOST), key_file_path=path,
                         timeout_connect=8)

    if not client.is_registered():
        try:
            client.register()
        except PyLGTVPairException:
            _LOGGER.error("Pairing with TV failed")
            return None
        except OSError:
            _LOGGER.error("TV unreachable")
            return None

    return LgWebOSNotificationService(client, config.get(CONF_ICON))


class LgWebOSNotificationService(BaseNotificationService):
    """Implement the notification service for LG WebOS TV."""

    def __init__(self, client, icon_path):
        """Initialize the service."""
        self._client = client
        self._icon_path = icon_path

    def send_message(self, message="", **kwargs):
        """Send a message to the tv."""
        from pylgtv import PyLGTVPairException

        try:
            data = kwargs.get(ATTR_DATA)
            icon_path = data.get(CONF_ICON, self._icon_path) if data else \
                self._icon_path
            self._client.send_message(message, icon_path=icon_path)
        except PyLGTVPairException:
            _LOGGER.error("Pairing with TV failed")
        except FileNotFoundError:
            _LOGGER.error("Icon %s not found", icon_path)
        except OSError:
            _LOGGER.error("TV unreachable")
