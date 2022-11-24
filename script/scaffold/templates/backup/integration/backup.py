"""Backup platform for the NEW_NAME integration."""
from spencerassistant.core import spencerAssistant


async def async_pre_backup(hass: spencerAssistant) -> None:
    """Perform operations before a backup starts."""


async def async_post_backup(hass: spencerAssistant) -> None:
    """Perform operations after a backup finishes."""
