"""
Allows utilizing telegram webhooks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/telegram_bot.webhooks/
"""
import asyncio
import datetime as dt
from ipaddress import ip_network
import logging

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.util import get_real_ip
from homeassistant.components.telegram_bot import (
    CONF_ALLOWED_CHAT_IDS, BaseTelegramBotEntity, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_API_KEY, EVENT_HOMEASSISTANT_STOP, HTTP_BAD_REQUEST,
    HTTP_UNAUTHORIZED, CONF_URL)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

TELEGRAM_HANDLER_URL = '/api/telegram_webhooks'
REMOVE_HANDLER_URL = ''

CONF_TRUSTED_NETWORKS = 'trusted_networks'

DEFAULT_TRUSTED_NETWORKS = [
    ip_network('149.154.167.197/32'),
    ip_network('149.154.167.198/31'),
    ip_network('149.154.167.200/29'),
    ip_network('149.154.167.208/28'),
    ip_network('149.154.167.224/29'),
    ip_network('149.154.167.232/31')
]

# pylint: disable=no-value-for-parameter
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_URL): vol.Url(),
    vol.Optional(CONF_TRUSTED_NETWORKS, default=DEFAULT_TRUSTED_NETWORKS):
        vol.All(cv.ensure_list, [ip_network])
})


@asyncio.coroutine
def async_setup_platform(hass, config):
    """Set up the Telegram webhooks platform."""
    import telegram
    bot = telegram.Bot(config[CONF_API_KEY])

    current_status = yield from hass.async_add_job(bot.getWebhookInfo)
    base_url = config.get(CONF_URL, hass.config.api.base_url)

    # Some logging of Bot current status:
    last_error_date = getattr(current_status, 'last_error_date', None)
    if (last_error_date is not None) and (isinstance(last_error_date, int)):
        last_error_date = dt.datetime.fromtimestamp(last_error_date)
        _LOGGER.info("telegram webhook last_error_date: %s. Status: %s",
                     last_error_date, current_status)
    else:
        _LOGGER.debug("telegram webhook Status: %s", current_status)

    handler_url = "{0}{1}".format(base_url, TELEGRAM_HANDLER_URL)
    if not handler_url.startswith('https'):
        _LOGGER.error("Invalid telegram webhook %s must be https", handler_url)
        return False

    if current_status and current_status['url'] != handler_url:
        result = yield from hass.async_add_job(bot.setWebhook, handler_url)
        if result:
            _LOGGER.info("Set new telegram webhook %s", handler_url)
        else:
            _LOGGER.error("Set telegram webhook failed %s", handler_url)
            return False

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        lambda event: bot.setWebhook(REMOVE_HANDLER_URL))
    hass.http.register_view(BotPushReceiver(
        hass, config[CONF_ALLOWED_CHAT_IDS], config[CONF_TRUSTED_NETWORKS]))
    return True


class BotPushReceiver(HomeAssistantView, BaseTelegramBotEntity):
    """Handle pushes from Telegram."""

    requires_auth = False
    url = TELEGRAM_HANDLER_URL
    name = 'telegram_webhooks'

    def __init__(self, hass, allowed_chat_ids, trusted_networks):
        """Initialize the class."""
        BaseTelegramBotEntity.__init__(self, hass, allowed_chat_ids)
        self.trusted_networks = trusted_networks

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
            return self.json_message('Invalid JSON', HTTP_BAD_REQUEST)

        if not self.process_message(data):
            return self.json_message('Invalid message', HTTP_BAD_REQUEST)
        else:
            return self.json({})
