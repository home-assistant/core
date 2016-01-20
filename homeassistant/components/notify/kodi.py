"""
homeassistant.components.notify.kodi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Kodi notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.kodi/
"""
import logging
from homeassistant.components import kodi

from homeassistant.components.notify import (
    ATTR_TITLE, BaseNotificationService)

DEPENDENCIES = ['kodi']
_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """ Get the kodi notification service. """

    notification_devs = []

    for _, device in kodi.get_kodi_devices():
        notification_devs.append(device)

    return KodiNotificationService(notification_devs)


# pylint: disable=too-few-public-methods
class KodiNotificationService(BaseNotificationService):
    """ Implements kodi notification service. """

    def __init__(self, notification_devs):
        self._notification_devs = notification_devs

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        for dev in self._notification_devs:
            assert isinstance(dev, kodi.KodiDevice)
            dev.api.GUI.ShowNotification(title, message)
