"""
Allows utilizing telegram webhooks or telegram polling.

See https://core.telegram.org/bots/webhooks for details
 about webhooks.

"""
import asyncio
import logging
from ipaddress import ip_network

import voluptuous as vol

from homeassistant.const import (
    HTTP_BAD_REQUEST, HTTP_UNAUTHORIZED, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_API_KEY
from homeassistant.components.http.util import get_real_ip
from homeassistant.core import callback

DOMAIN = 'telegram_webhooks'
DEPENDENCIES = ['http']
REQUIREMENTS = ['python-telegram-bot==5.3.0']

_LOGGER = logging.getLogger(__name__)

EVENT_TELEGRAM_COMMAND = 'telegram_command'
EVENT_TELEGRAM_TEXT = 'telegram_text'

CONF_POLL = 'poll'
CONF_WEBHOOK = 'webhook'
CONF_METHOD = 'method'

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
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_METHOD, default=CONF_WEBHOOK): vol.In(
            [CONF_POLL, CONF_WEBHOOK]),
        vol.Optional(CONF_TRUSTED_NETWORKS, default=DEFAULT_TRUSTED_NETWORKS):
            vol.All(cv.ensure_list, [ip_network]),
        vol.Required(CONF_USER_ID): {cv.string: cv.positive_int},
    }),
}, extra=vol.ALLOW_EXTRA)


class WrongMessageException(Exception):
    """Exception when message is wrong."""

    pass


class WrongUserException(Exception):
    """Exception when user_id is not allowed."""

    pass


class NoTextException(Exception):
    """Exception when no text is in the message."""

    pass


def setup(hass, config):
    """Setup the telegram_webhooks component."""
    import telegram

    conf = config[DOMAIN]
    bot = telegram.Bot(conf[CONF_API_KEY])
    if conf[CONF_METHOD] == CONF_WEBHOOK:
        return _setup_webhook(hass, conf, bot)
    else:
        return _setup_polling(hass, conf, bot)


def _setup_webhook(hass, conf, bot):
    if CONF_API_KEY in conf:

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


class BotReceiver:
    """Base receiver class."""

    def __init__(self, user_ids: dict):
        """Initialize the instance."""
        self.users = {user_id: dev_id for dev_id, user_id in
                      user_ids.items()}
        _LOGGER.debug("users allowed: %s", self.users)

    @asyncio.coroutine
    def process_message(self, data) -> ():
        """Check for basic message rules and prepare an event to be fired."""
        data = data.get('message')

        if not data or 'from' not in data or 'text' not in data:
            raise WrongMessageException()

        if data['from'].get('id') not in self.users:
            _LOGGER.warning("User not allowed")
            raise WrongUserException()

        _LOGGER.debug("Received telegram data: %s", data)
        if not data['text']:
            _LOGGER.warning('no text')
            raise NoTextException()

        if data['text'][:1] == '/':
            # telegram command "/blabla arg1 arg2 ..."
            pieces = data['text'].split(' ')

            return (EVENT_TELEGRAM_COMMAND, {
                ATTR_COMMAND: pieces[0],
                ATTR_ARGS: " ".join(pieces[1:]),
                ATTR_USER_ID: data['from']['id'],
            })

        # telegram text "bla bla"
        else:
            return (EVENT_TELEGRAM_TEXT, {
                ATTR_TEXT: data['text'],
                ATTR_USER_ID: data['from']['id'],
            })


class BotPushReceiver(HomeAssistantView, BotReceiver):
    """Handle pushes from telegram."""

    requires_auth = False
    url = TELEGRAM_HANDLER_URL
    name = "telegram_webhooks"

    def __init__(self, user_ids: dict, trusted_networks):
        """Initialize users allowed to send messages to bot."""
        self.trusted_networks = trusted_networks
        BotReceiver.__init__(self, user_ids)

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
        try:
            event, event_data = yield from self.process_message(data)
        except WrongMessageException:
            return self.json({})
        except WrongUserException:
            _LOGGER.warning("User not allowed")
            return self.json_message('Invalid user', HTTP_BAD_REQUEST)
        except NoTextException:
            _LOGGER.warning('no text')
            return self.json({})

        request.app['hass'].bus.async_fire(event, event_data)
        return self.json({})


def _setup_polling(hass, conf, bot):
    """The actual setup of the telegram component."""
    checker = BotPollReceiver(bot, hass, conf[CONF_USER_ID])

    @callback
    def _start_bot(_event):
        """Start the checking loop."""
        hass.loop.create_task(checker.check_incoming())

    @callback
    def _stop_bot(_event):
        """Stop the checking loop."""
        checker.checking = False

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START,
        _start_bot
    )
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        _stop_bot
    )

    # Return boolean to indicate that initialization was successfully.
    return True


class BotPollReceiver(BotReceiver):
    """asyncio telegram incoming message handler."""

    def __init__(self, bot, hass, user_ids):
        """Initialize the polling instance."""
        BotReceiver.__init__(self, user_ids)
        import aiohttp
        self.update_id = 0
        self.bot = bot
        self.hass = hass
        # boolean to check if checking loop should continue running
        self.checking = True
        self.session = aiohttp.ClientSession(loop=self.hass.loop)
        self.update_url = '{0}/getUpdates'.format(self.bot.base_url)

    @asyncio.coroutine
    def get_updates(self, offset, timeout):
        """Bypass the default getUpdates method to enable asyncio."""
        data = {'timeout': timeout}
        if offset:
            data['offset'] = offset

        resp = yield from self.session.post(
            self.update_url, data=data,
            headers={'connection': 'keep-alive'}
        )
        assert resp.status == 200
        try:
            _json = yield from resp.json()
            yield from resp.release()
            return _json
        except ValueError as ex:
            logging.exception(ex)
            resp.close()

    @asyncio.coroutine
    def handle(self):
        """" Receiving and processing incoming messages."""
        _updates = yield from self.get_updates(self.update_id, 10)
        for update in _updates['result']:
            self.update_id = update['update_id'] + 1
            try:
                event, event_data = yield from self.process_message(update)
            except WrongMessageException:
                return
            except WrongUserException:
                return
            except NoTextException:
                return

            self.hass.bus.async_fire(event, event_data)

    @asyncio.coroutine
    def check_incoming(self):
        """"Loop which continuously checks for incoming telegram messages."""
        while self.checking:
            try:
                yield from self.handle()
            except AssertionError:
                asyncio.sleep(5)
                raise
