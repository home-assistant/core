"""Helper functions for Telegram bot integration."""

from telegram import Bot

from .const import SIGNAL_UPDATE_EVENT


def signal(bot: Bot) -> str:
    """Define signal name."""
    return f"{SIGNAL_UPDATE_EVENT}_{bot.id}"


def get_base_url(bot: Bot) -> str:
    """Return the base URL for the bot."""
    return bot.base_url.replace(bot.token, "")
