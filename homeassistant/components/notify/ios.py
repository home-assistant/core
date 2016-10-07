"""
iOS push notification platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.ios/
"""
import logging
import requests

from homeassistant.components import ios

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_MESSAGE,
    ATTR_DATA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

PUSH_URL = "https://mj28d17jwj.execute-api.us-west-2.amazonaws.com/prod/push"

DEPENDENCIES = ['ios']


def get_service(hass, config):
    """Get the iOS notification service."""
    return iOSNotificationService()


# pylint: disable=too-few-public-methods, too-many-arguments, invalid-name
class iOSNotificationService(BaseNotificationService):
    """Implement the notification service for iOS."""

    def __init__(self):
        """Initialize the service."""

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        return ios.devices_with_push()

    def send_message(self, message="", **kwargs):
        """Send a message to the Lambda APNS gateway."""
        data = {ATTR_MESSAGE: message}

        if kwargs.get(ATTR_TITLE) is not None:
            # Remove default title from notifications.
            if kwargs.get(ATTR_TITLE) != ATTR_TITLE_DEFAULT:
                data[ATTR_TITLE] = kwargs.get(ATTR_TITLE)

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            targets = ios.enabled_push_ids()

        if kwargs.get(ATTR_DATA) is not None:
            data[ATTR_DATA] = kwargs.get(ATTR_DATA)

        for target in targets:
            data[ATTR_TARGET] = target

            response = requests.put(PUSH_URL, json=data, timeout=10)

            if response.status_code not in (200, 201):
                _LOGGER.exception(
                    'Error sending push notification. Response %d: %s:',
                    response.status_code, response.reason)
