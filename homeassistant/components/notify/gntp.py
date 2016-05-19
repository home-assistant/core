"""
GNTP (aka Growl) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.gntp/
"""
import logging
import os

from homeassistant.components.notify import (
    ATTR_TITLE, BaseNotificationService)

REQUIREMENTS = ['gntp==1.0.3']

_LOGGER = logging.getLogger(__name__)

_GNTP_LOGGER = logging.getLogger('gntp')
_GNTP_LOGGER.setLevel(logging.ERROR)


def get_service(hass, config):
    """Get the GNTP notification service."""
    if config.get('app_icon') is None:
        icon_file = os.path.join(os.path.dirname(__file__), "..", "frontend",
                                 "www_static", "favicon-192x192.png")
        app_icon = open(icon_file, 'rb').read()
    else:
        app_icon = config.get('app_icon')

    return GNTPNotificationService(config.get('app_name', 'HomeAssistant'),
                                   config.get('app_icon', app_icon),
                                   config.get('hostname', 'localhost'),
                                   config.get('password'),
                                   config.get('port', 23053))


# pylint: disable=too-few-public-methods
class GNTPNotificationService(BaseNotificationService):
    """Implement the notification service for GNTP."""

    # pylint: disable=too-many-arguments
    def __init__(self, app_name, app_icon, hostname, password, port):
        """Initialize the service."""
        import gntp.notifier
        import gntp.errors
        self.gntp = gntp.notifier.GrowlNotifier(
            applicationName=app_name,
            notifications=["Notification"],
            applicationIcon=app_icon,
            hostname=hostname,
            password=password,
            port=port
        )
        try:
            self.gntp.register()
        except gntp.errors.NetworkError:
            _LOGGER.error('Unable to register with the GNTP host.')
            return

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        self.gntp.notify(noteType="Notification", title=kwargs.get(ATTR_TITLE),
                         description=message)
