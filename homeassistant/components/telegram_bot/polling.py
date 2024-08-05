"""Support for Telegram bot using polling."""

import logging

from telegram import Update
from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut
from telegram.ext import ApplicationBuilder, CallbackContext, TypeHandler

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

from . import BaseTelegramBotEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, bot, config):
    """Set up the Telegram polling platform."""
    pollbot = PollBot(hass, bot, config)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, pollbot.start_polling)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, pollbot.stop_polling)

    return True


async def process_error(update: Update, context: CallbackContext) -> None:
    """Telegram bot error handler."""
    try:
        if context.error:
            raise context.error
    except (TimedOut, NetworkError, RetryAfter):
        # Long polling timeout or connection problem. Nothing serious.
        pass
    except TelegramError:
        _LOGGER.error('Update "%s" caused error: "%s"', update, context.error)


class PollBot(BaseTelegramBotEntity):
    """Controls the Application object that holds the bot and an updater.

    The application is set up to pass telegram updates to `self.handle_update`
    """

    def __init__(self, hass, bot, config):
        """Create Application to poll for updates."""
        super().__init__(hass, config)
        self.bot = bot
        self.application = ApplicationBuilder().bot(self.bot).build()
        self.application.add_handler(TypeHandler(Update, self.handle_update))
        self.application.add_error_handler(process_error)

    async def start_polling(self, event=None):
        """Start the polling task."""
        _LOGGER.debug("Starting polling")
        await self.application.initialize()
        await self.application.updater.start_polling()
        await self.application.start()

    async def stop_polling(self, event=None):
        """Stop the polling task."""
        _LOGGER.debug("Stopping polling")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
