"""
Telegram bot polling implementation.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/telegram_bot.polling/
"""
import asyncio
from asyncio.futures import CancelledError
import logging

import async_timeout
from aiohttp.client_exceptions import ClientError
from aiohttp.hdrs import CONNECTION, KEEP_ALIVE

from homeassistant.components.telegram_bot import (
    CONF_ALLOWED_CHAT_IDS, BaseTelegramBotEntity,
    PLATFORM_SCHEMA as TELEGRAM_PLATFORM_SCHEMA)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, CONF_API_KEY)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = TELEGRAM_PLATFORM_SCHEMA
RETRY_SLEEP = 10


class WrongHttpStatus(Exception):
    """Thrown when a wrong http status is received."""

    pass


@asyncio.coroutine
def async_setup_platform(hass, config):
    """Set up the Telegram polling platform."""
    import telegram
    bot = telegram.Bot(config[CONF_API_KEY])
    pol = TelegramPoll(bot, hass, config[CONF_ALLOWED_CHAT_IDS])

    @callback
    def _start_bot(_event):
        """Start the bot."""
        pol.start_polling()

    @callback
    def _stop_bot(_event):
        """Stop the bot."""
        pol.stop_polling()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _start_bot)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_bot)

    return True


class TelegramPoll(BaseTelegramBotEntity):
    """Asyncio telegram incoming message handler."""

    def __init__(self, bot, hass, allowed_chat_ids):
        """Initialize the polling instance."""
        BaseTelegramBotEntity.__init__(self, hass, allowed_chat_ids)
        self.update_id = 0
        self.websession = async_get_clientsession(hass)
        self.update_url = '{0}/getUpdates'.format(bot.base_url)
        self.polling_task = None  # The actual polling task.
        self.timeout = 15  # async post timeout
        # Polling timeout should always be less than async post timeout.
        self.post_data = {'timeout': self.timeout - 5}

    def start_polling(self):
        """Start the polling task."""
        self.polling_task = self.hass.async_add_job(self.check_incoming())

    def stop_polling(self):
        """Stop the polling task."""
        self.polling_task.cancel()

    @asyncio.coroutine
    def get_updates(self, offset):
        """Bypass the default long polling method to enable asyncio."""
        resp = None
        if offset:
            self.post_data['offset'] = offset
        try:
            with async_timeout.timeout(self.timeout, loop=self.hass.loop):
                resp = yield from self.websession.post(
                    self.update_url, data=self.post_data,
                    headers={CONNECTION: KEEP_ALIVE}
                )
            if resp.status == 200:
                _json = yield from resp.json()
                return _json
            else:
                raise WrongHttpStatus('wrong status {}'.format(resp.status))
        finally:
            if resp is not None:
                yield from resp.release()

    @asyncio.coroutine
    def check_incoming(self):
        """Continuously check for incoming telegram messages."""
        try:
            while True:
                try:
                    _updates = yield from self.get_updates(self.update_id)
                except (WrongHttpStatus, ClientError) as err:
                    # WrongHttpStatus: Non-200 status code.
                    # Occurs at times (mainly 502) and recovers
                    # automatically. Pause for a while before retrying.
                    _LOGGER.error(err)
                    yield from asyncio.sleep(RETRY_SLEEP)
                except (asyncio.TimeoutError, ValueError):
                    # Long polling timeout. Nothing serious.
                    # Json error. Just retry for the next message.
                    pass
                else:
                    # no exception raised. update received data.
                    _updates = _updates.get('result')
                    if _updates is None:
                        _LOGGER.error("Incorrect result received.")
                    else:
                        for update in _updates:
                            self.update_id = update['update_id'] + 1
                            self.process_message(update)
        except CancelledError:
            _LOGGER.debug("Stopping Telegram polling bot")
