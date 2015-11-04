"""
homeassistant.components.notify.slack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Slack platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.slack.html
"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

REQUIREMENTS = ['slacker==0.6.8']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def get_service(hass, config):
    """ Get the slack notification service. """

    if not validate_config(config,
                           {DOMAIN: ['default_channel', CONF_API_KEY]},
                           _LOGGER):
        return None

    try:
        # pylint: disable=no-name-in-module, unused-variable
        from slacker import Error as SlackError

    except ImportError:
        _LOGGER.exception(
            "Unable to import slacker. "
            "Did you maybe not install the 'slacker.py' package?")

        return None

    try:
        api_token = config[DOMAIN].get(CONF_API_KEY)

        return SlackNotificationService(
            config[DOMAIN]['default_channel'],
            api_token)

    except SlackError as ex:
        _LOGGER.error(
            "Slack authentication failed")
        _LOGGER.exception(ex)


# pylint: disable=too-few-public-methods
class SlackNotificationService(BaseNotificationService):
    """ Implements notification service for Slack. """

    def __init__(self, default_channel, api_token):
        from slacker import Slacker
        self._default_channel = default_channel
        self._api_token = api_token
        self.slack = Slacker(self._api_token)
        self.slack.auth.test()

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        from slacker import Error as SlackError
        channel = kwargs.get('channel', self._default_channel)
        try:
            self.slack.chat.post_message(channel, message)
        except SlackError as ex:
            _LOGGER.exception("Could not send slack notification")
            _LOGGER.exception(ex)
