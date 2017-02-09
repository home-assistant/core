"""
Allows utilizing telegram webhooks.

See https://core.telegram.org/bots/webhooks for details
 about webhooks.

"""
import asyncio
import logging
from ipaddress import ip_network

import voluptuous as vol

from homeassistant.const import (
    HTTP_BAD_REQUEST, HTTP_UNAUTHORIZED)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_API_KEY
from homeassistant.components.http.util import get_real_ip

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-telegram-bot==5.3.0']

EVENT_TELEGRAM_COMMAND = 'telegram.command'

CONF_USER_ID = 'user_id'
CONF_TRUSTED_NETWORKS = 'trusted_networks'
DEFAULT_TRUSTED_NETWORKS = [
    ip_network('149.154.167.197/32'),
    ip_network('149.154.167.198/31'),
    ip_network('149.154.167.200/29'),
    ip_network('149.154.167.208/28'),
    ip_network('149.154.167.224/29'),
    ip_network('149.154.167.232/31')]
ATTR_COMMAND = 'command'
ATTR_USER_ID = 'user_id'
ATTR_ARGS = 'args'

DEPENDENCIES = ['http']
DOMAIN = 'telegram_webhooks'
CONF_HANDLER_URL = '/api/telegram_webhooks'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_KEY, default=''): cv.string,
        vol.Optional(CONF_TRUSTED_NETWORKS, default=DEFAULT_TRUSTED_NETWORKS):
            vol.All(cv.ensure_list, [ip_network]),
        vol.Required(CONF_USER_ID): {cv.string: cv.positive_int},
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the telegram_webhooks component.

    register webhook if API_KEY is specified
    register /api/telegram_webhooks as web service for telegram bot
    """
    import telegram

    config = config[DOMAIN]

    if config.get(CONF_API_KEY, ''):
        bot = telegram.Bot(config[CONF_API_KEY])
        current_status = bot.getWebhookInfo()
        _LOGGER.debug("telegram webhook status: %s", current_status)
        handler_url = hass.config.api.base_url + CONF_HANDLER_URL
        if current_status and current_status['url'] != handler_url:
            if bot.setWebhook(config[CONF_API_URL]):
                _LOGGER.info("set new telegram webhook %s", handler_url)
            else:
                _LOGGER.error("setting telegram webhook failed %s", handler_url)

    hass.http.register_view(BotPushReceiver(config[CONF_USER_ID],
                                            config[CONF_TRUSTED_NETWORKS]))
    return True


class BotPushReceiver(HomeAssistantView):
    """Handle pushes from telegram."""

    requires_auth = False
    url = CONF_HANDLER_URL
    name = "telegram_webhooks"

    def __init__(self, user_id_array, trusted_networks):
        """Initialize users allowed to send messages to bot."""
        self.trusted_networks = trusted_networks
        self.users = dict([(user_id, dev_id)
                           for (dev_id, user_id) in user_id_array.items()])
        _LOGGER.debug("users allowed: %s", self.users)

    @asyncio.coroutine
    def post(self, request):
        """Accept the POST from telegram."""
        real_ip = get_real_ip(request)
        if not any([real_ip in net for net in self.trusted_networks]):
            _LOGGER.warning("Access denied from %s", real_ip)
            return self.json_message('Access denied', HTTP_UNAUTHORIZED)

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

        pieces = data['text'].split(' ')

        request.app['hass'].bus.async_fire(EVENT_TELEGRAM_COMMAND, {
            ATTR_COMMAND: pieces[0],
            ATTR_ARGS: " ".join(pieces[1:]),
            ATTR_USER_ID: data['from']['id'],
            })
        return self.json({})
