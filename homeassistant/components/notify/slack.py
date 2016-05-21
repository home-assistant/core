"""
Slack platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.slack/
"""
import logging

from homeassistant.components.notify import DOMAIN, BaseNotificationService
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import validate_config

REQUIREMENTS = ['slacker==0.9.10']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def get_service(hass, config):
    """Get the Slack notification service."""
    import slacker

    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['default_channel', CONF_API_KEY]},
                           _LOGGER):
        return None

    try:
        return SlackNotificationService(
            config['default_channel'],
            config[CONF_API_KEY])

    except slacker.Error:
        _LOGGER.exception(
            "Slack authentication failed")
        return None


# pylint: disable=too-few-public-methods
class SlackNotificationService(BaseNotificationService):
    """Implement the notification service for Slack."""

    def __init__(self, default_channel, api_token):
        """Initialize the service."""
        from slacker import Slacker
        self._default_channel = default_channel
        self._api_token = api_token
        self.slack = Slacker(self._api_token)
        self.slack.auth.test()

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        import slacker

        channel = kwargs.get('target') or self._default_channel
        try:
            self.slack.chat.post_message(channel, message)
        except slacker.Error:
            _LOGGER.exception("Could not send slack notification")
