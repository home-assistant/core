"""Support for Telegram bot using polling."""
import logging

from telegram import Update
from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut
from telegram.ext import CallbackContext, TypeHandler, Updater

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

from . import BaseTelegramBotEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, bot, config):
    """Set up the Telegram polling platform."""
    pollbot = PollBot(hass, bot, config)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, pollbot.start_polling)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, pollbot.stop_polling)

    return True


def process_error(update: Update, context: CallbackContext) -> None:
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
    """
    Controls the Updater object that holds the bot and a dispatcher.

    The dispatcher is set up by the super class to pass telegram updates to `self.handle_update`
    """

    def __init__(self, hass, bot, config):
        """Create Updater and Dispatcher before calling super()."""
        self.bot = bot
        self.updater = Updater(bot=bot, workers=4)
        self.dispatcher = self.updater.dispatcher
        self.dispatcher.add_handler(TypeHandler(Update, self.handle_update))
        self.dispatcher.add_error_handler(process_error)
        super().__init__(hass, config)

    def start_polling(self, event=None):
        """Start the polling task."""
        _LOGGER.debug("Starting polling")
        self.updater.start_polling()

    def stop_polling(self, event=None):
        """Stop the polling task."""
        _LOGGER.debug("Stopping polling")
        self.updater.stop()
