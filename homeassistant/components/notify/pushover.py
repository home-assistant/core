"""
Pushover platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushover/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

from . import (
    ATTR_DATA, ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA,
    BaseNotificationService)

REQUIREMENTS = ['python-pushover==0.3']
_LOGGER = logging.getLogger(__name__)


CONF_USER_KEY = 'user_key'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USER_KEY): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Pushover notification service."""
    from pushover import InitError

    try:
        return PushoverNotificationService(
            config[CONF_USER_KEY], config[CONF_API_KEY])
    except InitError:
        _LOGGER.error("Wrong API key supplied")
        return None


class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(self, user_key, api_token):
        """Initialize the service."""
        from pushover import Client
        self._user_key = user_key
        self._api_token = api_token
        self.pushover = Client(
            self._user_key, api_token=self._api_token)

    def send_message(self, message='', **kwargs):
        """Send a message to a user."""
        from pushover import RequestError

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
                self.pushover.send_message(message, **data)
            except ValueError as val_err:
                _LOGGER.error(str(val_err))
            except RequestError:
                _LOGGER.exception("Could not send pushover notification")
