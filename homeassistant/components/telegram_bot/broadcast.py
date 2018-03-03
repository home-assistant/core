"""
Telegram bot implementation to send messages only.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/telegram_bot.broadcast/
"""
import asyncio
import logging

from homeassistant.components.telegram_bot import (
    PLATFORM_SCHEMA as TELEGRAM_PLATFORM_SCHEMA,
    CONF_PROXY_URL, CONF_PROXY_PARAMS)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = TELEGRAM_PLATFORM_SCHEMA


@asyncio.coroutine
def async_setup_platform(hass, config):
    """Set up the Telegram broadcast platform."""
    # Check the API key works
    from telegram import Bot
    from telegram.utils.request import Request

    api_key = config.get(CONF_API_KEY)
    proxy_url = config.get(CONF_PROXY_URL)
    proxy_params = config.get(CONF_PROXY_PARAMS)

    request = None
    if proxy_url is not None:
        request = Request(proxy_url=proxy_url,
                          urllib3_proxy_kwargs=proxy_params)
    bot = Bot(token=api_key, request=request)

    bot_config = yield from hass.async_add_job(bot.getMe)
    _LOGGER.debug("Telegram broadcast platform setup with bot %s",
                  bot_config['username'])
    return True
