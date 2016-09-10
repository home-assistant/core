"""
Kodi notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.kodi/
"""
import logging

from homeassistant.components.notify import (ATTR_TITLE, ATTR_TITLE_DEFAULT,
                                             ATTR_DATA,
                                             BaseNotificationService)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['jsonrpc-requests==0.3']

ATTR_DISPLAYTIME = 'displaytime'
ATTR_ICON = 'icon'


def get_service(hass, config):
    """Return the notify service."""
    url = '{}:{}'.format(config.get('host'), config.get('port', '8080'))

    auth = (config.get('username', ''),
            config.get('password', ''))

    return KODINotificationService(
        config.get('name', 'Kodi'),
        url,
        auth
    )


# pylint: disable=too-few-public-methods
class KODINotificationService(BaseNotificationService):
    """Implement the notification service for Kodi."""
    def __init__(self, name, url, auth=None):
        """Initialize the service."""
        import jsonrpc_requests
        self._name = name
        self._url = url
        self._server = jsonrpc_requests.Server(
            '{}/jsonrpc'.format(self._url),
            auth=auth,
            timeout=5)

    def send_message(self, message="", **kwargs):
        """Send a message to Kodi."""
        import jsonrpc_requests
        try:
            data = kwargs.get(ATTR_DATA)
            displaytime = 10000
            icon = "info"

            if data is not None and ATTR_DISPLAYTIME in data:
                displaytime = data.get(ATTR_DISPLAYTIME, 10000)

            if data is not None and ATTR_ICON in data:
                icon = data.get(ATTR_ICON, "info")

            title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
            self._server.GUI.ShowNotification(title, message, icon,
                                              displaytime)

        except jsonrpc_requests.jsonrpc.TransportError:
            _LOGGER.warning('Unable to fetch kodi data, Is kodi online?')

        except Exception as exception:
            _LOGGER.warning('Error: "%s"', exception)
