"""Backup platform for the Recorder integration."""
from logging import getLogger

from homeassistant.core import HomeAssistant

from . import Recorder
from .const import DATA_INSTANCE

_LOGGER = getLogger(__name__)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Perform operations before a backup starts."""
    _LOGGER.info("Backup start notification, locking database for writes")
    instance: Recorder = hass.data[DATA_INSTANCE]
    await instance.lock_database()


async def async_post_backup(hass: HomeAssistant) -> None:
    """Perform operations after a backup finishes."""
    instance: Recorder = hass.data[DATA_INSTANCE]
    _LOGGER.info("Backup end notification, releasing write lock")
    instance.unlock_database()
