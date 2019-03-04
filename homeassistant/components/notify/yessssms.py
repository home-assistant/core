"""
Support for the YesssSMS platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.yessssms/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_RECIPIENT
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['YesssSMS==0.2.3']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the YesssSMS notification service."""
    return YesssSMSNotificationService(
        config[CONF_USERNAME], config[CONF_PASSWORD], config[CONF_RECIPIENT])


class YesssSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the YesssSMS service."""

    def __init__(self, username, password, recipient):
        """Initialize the service."""
        from YesssSMS import YesssSMS
        self.yesss = YesssSMS(username, password)
        self._recipient = recipient
        _LOGGER.debug(
            "initialized; library version: %s", self.yesss.version())

    def send_message(self, message="", **kwargs):
        """Send a SMS message via Yesss.at's website."""
        if self.yesss.account_is_suspended():
            # only retry to login after HASS was restarted with (hopefully)
            # new login data.
            _LOGGER.error(
                "Account is suspended, cannot send SMS. "
                "Check your login data and restart Home Assistant")
            return
        try:
            self.yesss.send(self._recipient, message)
        except self.yesss.NoRecipientError as ex:
            _LOGGER.error(
                "You need to provide a recipient for SMS notification: %s",
                ex)
        except self.yesss.EmptyMessageError as ex:
            _LOGGER.error(
                "Cannot send empty SMS message: %s", ex)
        except self.yesss.SMSSendingError as ex:
            _LOGGER.error(str(ex), exc_info=ex)
        except ConnectionError as ex:
            _LOGGER.error(
                "YesssSMS: unable to connect to yesss.at server.",
                exc_info=ex)
        except self.yesss.AccountSuspendedError as ex:
            _LOGGER.error(
                "Wrong login credentials!! Verify correct credentials and "
                "restart Home Assistant: %s", ex)
        except self.yesss.LoginError as ex:
            _LOGGER.error("Wrong login credentials: %s", ex)
        else:
            _LOGGER.info("SMS sent")
