"""Telegram bot polling implementation."""

import asyncio
from asyncio.futures import CancelledError
import logging


from homeassistant.components.telegram_bot import CONF_ALLOWED_CHAT_IDS, \
    process_message
from homeassistant.const import EVENT_HOMEASSISTANT_START, \
    EVENT_HOMEASSISTANT_STOP, CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp.errors import ClientError, ClientDisconnectedError
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-telegram-bot==5.3.0']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the polling platform."""
    import telegram
    bot = telegram.Bot(config[CONF_API_KEY])
    allowed_chat_ids = config[CONF_ALLOWED_CHAT_IDS]
    pol = TelegramPoll(bot, hass, allowed_chat_ids)

    @callback
    def _start_bot(_event):
        """Start the bot."""
        pol.start_polling()

    @callback
    def _stop_bot(_event):
        """Stop the bot."""
        pol.stop_polling()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START,
        _start_bot
    )
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        _stop_bot
    )
    async_add_devices(pol)


class TelegramPoll:
    """asyncio telegram incoming message handler."""

    def __init__(self, bot, hass, allowed_chat_ids):
        """Initialize the polling instance."""
        self.allowed_chat_ids = allowed_chat_ids
        self.update_id = 0
        self.hass = hass
        self.websession = async_get_clientsession(hass)
        self.update_url = '{0}/getUpdates'.format(bot.base_url)
        self.polling_task = None  # The actuall polling task.

    def start_polling(self):
        """Start the polling task."""
        self.polling_task = self.hass.async_add_job(self.check_incoming())

    def stop_polling(self):
        """Stop the polling task."""
        self.polling_task.cancel()

    @asyncio.coroutine
    def get_updates(self, offset, timeout):
        """Bypass the default longpolling method to enable asyncio."""
        resp = None
        _json = []  # The actual value to be returned.
        data = {'timeout': timeout}
        if offset:
            data['offset'] = offset
        try:
            resp = yield from self.websession.post(
                self.update_url, data=data,
                headers={'connection': 'keep-alive'}
            )
            if resp.status != 200:
                _LOGGER.error("Error {0} on {1}".format(
                    resp.status, self.update_url))
            _json = yield from resp.json()
        except ValueError:
            _LOGGER.error("Error parsing Json message")
        except (asyncio.TimeoutError, ClientError, ClientDisconnectedError):
            _LOGGER.error("Client connection error")
        finally:
            if resp is not None:
                yield from resp.release()

        return _json

    @asyncio.coroutine
    def handle(self):
        """" Receiving and processing incoming messages."""
        _updates = yield from self.get_updates(self.update_id, 10)
        for update in _updates['result']:
            self.update_id = update['update_id'] + 1
            event, event_data = yield from process_message(
                update, self.allowed_chat_ids)
            if event is None or event_data is None:
                return

            self.hass.bus.async_fire(event, event_data)

    @asyncio.coroutine
    def check_incoming(self):
        """"Loop which continuously checks for incoming telegram messages."""
        try:
            while True:
                # Each handle call sends a long polling post request
                # to the telegram server. If no incoming message it will return
                # an empty list. Calling self.handle() without any delay or
                # timeout will for this reason not really stress the processor.
                yield from self.handle()
        except CancelledError:
            _LOGGER.error("Stopping telegram polling")
            return
