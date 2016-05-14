"""
Google Voice SMS platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.google_voice/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TARGET, DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['https://github.com/w1ll1am23/pygooglevoice-sms/archive/'
                '7c5ee9969b97a7992fc86a753fe9f20e3ffa3f7c.zip#'
                'pygooglevoice-sms==0.0.1']


def get_service(hass, config):
    """Get the Google Voice SMS notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_USERNAME,
                                     CONF_PASSWORD]},
                           _LOGGER):
        return None

    return GoogleVoiceSMSNotificationService(config[CONF_USERNAME],
                                             config[CONF_PASSWORD])


# pylint: disable=too-few-public-methods
class GoogleVoiceSMSNotificationService(BaseNotificationService):
    """Implement the notification service for the Google Voice SMS service."""

    def __init__(self, username, password):
        """Initialize the service."""
        from googlevoicesms import Voice
        self.voice = Voice()
        self.username = username
        self.password = password

    def send_message(self, message="", **kwargs):
        """Send SMS to specified target user cell."""
        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            _LOGGER.info('At least 1 target is required')
            return

        if not isinstance(targets, list):
            targets = [targets]

        self.voice.login(self.username, self.password)

        for target in targets:
            self.voice.send_sms(target, message)

        self.voice.logout()
