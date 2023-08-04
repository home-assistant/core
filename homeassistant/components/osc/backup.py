"""Backup platform for the OSC (Open Sound Control) integration."""
from homeassistant.core import HomeAssistant


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Perform operations before a backup starts."""


async def async_post_backup(hass: HomeAssistant) -> None:
    """Perform operations after a backup finishes."""
