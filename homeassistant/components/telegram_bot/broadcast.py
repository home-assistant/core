"""Support for Telegram bot to send messages only."""
import logging

from . import PLATFORM_SCHEMA as TELEGRAM_PLATFORM_SCHEMA, initialize_bot

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = TELEGRAM_PLATFORM_SCHEMA


async def async_setup_platform(hass, config):
    """Set up the Telegram broadcast platform."""
    bot = initialize_bot(config)

    bot_config = await hass.async_add_job(bot.getMe)
    _LOGGER.debug("Telegram broadcast platform setup with bot %s",
                  bot_config['username'])
    return True
