"""Support for Telegram bot to send messages only."""
import logging

from . import initialize_bot

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config):
    """Set up the Telegram broadcast platform."""
    bot = initialize_bot(config)

    bot_config = await hass.async_add_job(bot.getMe)
    _LOGGER.debug(
        "Telegram broadcast platform setup with bot %s", bot_config["username"]
    )
    return True
