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

DOMAIN = 'telegram_webhooks'
DEPENDENCIES = ['http']
REQUIREMENTS = ['python-telegram-bot==5.3.0']

_LOGGER = logging.getLogger(__name__)

EVENT_TELEGRAM_COMMAND = 'telegram_command'
EVENT_TELEGRAM_TEXT = 'telegram_text'

TELEGRAM_HANDLER_URL = '/api/telegram_webhooks'

CONF_USER_ID = 'user_id'
CONF_TRUSTED_NETWORKS = 'trusted_networks'
DEFAULT_TRUSTED_NETWORKS = [
    ip_network('149.154.167.197/32'),
    ip_network('149.154.167.198/31'),
    ip_network('149.154.167.200/29'),
    ip_network('149.154.167.208/28'),
    ip_network('149.154.167.224/29'),
    ip_network('149.154.167.232/31')
]

ATTR_COMMAND = 'command'
ATTR_TEXT = 'text'
ATTR_USER_ID = 'user_id'
ATTR_ARGS = 'args'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_KEY): cv.string,
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

    conf = config[DOMAIN]

    if CONF_API_KEY in conf:
        bot = telegram.Bot(conf[CONF_API_KEY])
        current_status = bot.getWebhookInfo()
        _LOGGER.debug("telegram webhook status: %s", current_status)
        handler_url = "{0}{1}".format(hass.config.api.base_url,
                                      TELEGRAM_HANDLER_URL)
        if current_status and current_status['url'] != handler_url:
            if bot.setWebhook(handler_url):
                _LOGGER.info("set new telegram webhook %s", handler_url)
            else:
                _LOGGER.error("set telegram webhook failed %s", handler_url)

    hass.http.register_view(BotPushReceiver(conf[CONF_USER_ID],
                                            conf[CONF_TRUSTED_NETWORKS]))
    return True


class BotPushReceiver(HomeAssistantView):
    """Handle pushes from telegram."""

    requires_auth = False
    url = TELEGRAM_HANDLER_URL
    name = "telegram_webhooks"

    def __init__(self, user_id_array, trusted_networks):
        """Initialize users allowed to send messages to bot."""
        self.trusted_networks = trusted_networks
        self.users = {user_id: dev_id for dev_id, user_id in
                      user_id_array.items()}
        _LOGGER.debug("users allowed: %s", self.users)

    @asyncio.coroutine
    def post(self, request):
        """Accept the POST from telegram."""
        real_ip = get_real_ip(request)
        if not any(real_ip in net for net in self.trusted_networks):
            _LOGGER.warning("Access denied from %s", real_ip)
            return self.json_message('Access denied', HTTP_UNAUTHORIZED)

        try:
            data = yield from request.json()
        except ValueError:
            _LOGGER.error("Received telegram data: %s", data)
            return self.json_message('Invalid JSON', HTTP_BAD_REQUEST)

        # check for basic message rules
        data = data.get('message')
        if not data or 'from' not in data or 'text' not in data:
            return self.json({})

        if data['from'].get('id') not in self.users:
            _LOGGER.warning("User not allowed")
            return self.json_message('Invalid user', HTTP_BAD_REQUEST)

        _LOGGER.debug("Received telegram data: %s", data)
        if not data['text']:
            _LOGGER.warning('no text')
            return self.json({})

        if data['text'][:1] == '/':
            # telegram command "/blabla arg1 arg2 ..."
            pieces = data['text'].split(' ')

            request.app['hass'].bus.async_fire(EVENT_TELEGRAM_COMMAND, {
                ATTR_COMMAND: pieces[0],
                ATTR_ARGS: " ".join(pieces[1:]),
                ATTR_USER_ID: data['from']['id'],
                })

        # telegram text "bla bla"
        request.app['hass'].bus.async_fire(EVENT_TELEGRAM_TEXT, {
            ATTR_TEXT: data['text'],
            ATTR_USER_ID: data['from']['id'],
            })

        return self.json({})
