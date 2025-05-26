"""Support for Telegram bot to send messages only."""

from telegram import Bot

from homeassistant.core import HomeAssistant

from . import BaseTelegramBotEntity, TelegramBotConfigEntry


async def async_setup_platform(
    hass: HomeAssistant, bot: Bot, config: TelegramBotConfigEntry
) -> type[BaseTelegramBotEntity] | None:
    """Set up the Telegram broadcast platform."""
    return None
