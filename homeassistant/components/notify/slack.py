"""
Slack platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.slack/
"""
import logging

from homeassistant.components.notify import DOMAIN, BaseNotificationService
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers import validate_config

REQUIREMENTS = ['slacker==0.9.24']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the Slack notification service."""
    import slacker

    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['default_channel', CONF_API_KEY]},
                           _LOGGER):
        return False

    try:
        add_devices([SlackNotificationService(
            config.get('default_channel'),
            config.get(CONF_API_KEY),
            config.get(CONF_NAME))])

    except slacker.Error:
        _LOGGER.exception("Slack authentication failed")
        return False


# pylint: disable=too-few-public-methods,abstract-method
class SlackNotificationService(BaseNotificationService):
    """Implement the notification service for Slack."""

    def __init__(self, default_channel, api_token, name):
        """Initialize the service."""
        from slacker import Slacker
        self._default_channel = default_channel
        self._api_token = api_token
        self._name = name
        self.slack = Slacker(self._api_token)
        self.slack.auth.test()

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message, **kwargs):
        """Send a message to a user."""
        import slacker

        channel = kwargs.get('target') or self._default_channel
        try:
            self.slack.chat.post_message(channel, message)
        except slacker.Error:
            _LOGGER.exception("Could not send slack notification")
