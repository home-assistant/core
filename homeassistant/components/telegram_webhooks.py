"""
Allows utilizing telegram webhooks.

See https://core.telegram.org/bots/webhooks for details
 about webhooks.

"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import HTTP_BAD_REQUEST
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_API_KEY
from homeassistant.components.notify.telegram import REQUIREMENTS as REQ_NOTIFY

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = REQ_NOTIFY

CONF_USER_ID = 'user_id'
CONF_API_URL = 'api_url'

DEPENDENCIES = ['http']
DOMAIN = 'telegram_webhooks'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_KEY, default=''): cv.string,
        vol.Optional(CONF_API_URL, default=''): cv.string,
        vol.Required(CONF_USER_ID): {cv.string: cv.positive_int},
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the telegram_webhooks component.

    register webhook if API_KEY and API_URL specified
    register /api/telegram_webhooks as web service for telegram bot
    """
    import telegram

    config = config[DOMAIN]

    if config.get(CONF_API_KEY, '') and config.get(CONF_API_URL, ''):
        bot = telegram.Bot(config[CONF_API_KEY])
        current_status = bot.getWebhookInfo()
        _LOGGER.debug("telegram webhook status: %s", current_status)
        if current_status and current_status['url'] != config[CONF_API_URL]:
            if bot.setWebhook(config[CONF_API_URL]):
                _LOGGER.info("set new telegram webhook")
            else:
                _LOGGER.error("telegram webhook failed")

    hass.http.register_view(TelegrambotPushReceiver(config[CONF_USER_ID]))
    hass.states.set('{}.command'.format(DOMAIN), '')
    return True


class TelegrambotPushReceiver(HomeAssistantView):
    """Handle pushes from telegram."""

    requires_auth = False
    url = "/api/telegram_webhooks"
    name = "telegram_webhooks"

    def __init__(self, user_id_array):
        """Initialize users allowed to send messages to bot."""
        self.users = dict([(user_id, dev_id)
                           for (dev_id, user_id) in user_id_array.items()])
        _LOGGER.debug("users allowed: %s", self.users)

    @asyncio.coroutine
    def post(self, request):
        """Accept the POST from telegram."""
        try:
            data = yield from request.json()
            data = data['message']
        except (ValueError, IndexError):
            return self.json_message('Invalid JSON', HTTP_BAD_REQUEST)

        try:
            assert data['from']['id'] in self.users
        except (AssertionError, IndexError):
            _LOGGER.warning("User not allowed")
            return self.json_message('Invalid user', HTTP_BAD_REQUEST)

        _LOGGER.debug("Received telegram data: %s", data)
        try:
            assert data['text'][0] == '/'
        except (AssertionError, IndexError):
            _LOGGER.warning('no command')
            return self.json({})

        request.app['hass'].states.async_set('{}.command'.format(DOMAIN),
                                             data['text'], force_update=True)
        request.app['hass'].states.async_set('{}.user_id'.format(DOMAIN),
                                             data['from']['id'],
                                             force_update=True)
        return self.json({})
