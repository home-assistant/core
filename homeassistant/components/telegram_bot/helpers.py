"""Helper functions for Telegram bot integration."""

from telegram import Bot

from .const import SIGNAL_UPDATE_EVENT


def signal(bot: Bot) -> str:
    """Define signal name."""
    return f"{SIGNAL_UPDATE_EVENT}_{bot.id}"
