"""
Telegram bot implementation to send messages only.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/telegram_bot.broadcast/
"""
import asyncio
import logging

from homeassistant.components.telegram_bot import (
    initialize_bot,
    PLATFORM_SCHEMA as TELEGRAM_PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = TELEGRAM_PLATFORM_SCHEMA


@asyncio.coroutine
def async_setup_platform(hass, config):
    """Set up the Telegram broadcast platform."""
    # Check the API key works

    bot = initialize_bot(config)

    bot_config = yield from hass.async_add_job(bot.getMe)
    _LOGGER.debug("Telegram broadcast platform setup with bot %s",
                  bot_config['username'])
    return True
