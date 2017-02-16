"""
Pushsafer platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushsafer/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_TARGET, ATTR_DATA,
    BaseNotificationService)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-pushsafer==0.2']
_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})


# pylint: disable=unused-variable
def get_service(hass, config, discovery_info=None):
    """Get the Pushsafer notification service."""
    from pushsafer import InitError

    try:
        return PushsaferNotificationService(config[CONF_API_KEY])
    except InitError:
        _LOGGER.error(
            'Wrong private key supplied. Get it at https://www.pushsafer.com')
        return None


class PushsaferNotificationService(BaseNotificationService):
    """Implement the notification service for Pushsafer."""

    def __init__(self, privatekey):
        """Initialize the service."""
        from pushsafer import Client
        self._privatekey = privatekey
        self.pushsafer = Client(
            "", privatekey=self._privatekey)

    def send_message(self, message='', **kwargs):
        """Send a message to a user."""
        # Make a copy and use empty dict if necessary
        data = dict(kwargs.get(ATTR_DATA) or {})

        data['title'] = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        targets = kwargs.get(ATTR_TARGET)

        if not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            if target is not None:
                data['device'] = target

            try:
                self.pushsafer.send_message(message, data['title'], "", "",
                                            "", "", "", "",
                                            "0", "", "", "")
            except ValueError as val_err:
                _LOGGER.error(str(val_err))
