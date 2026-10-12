"""Backup platform for the KNX integration."""

import asyncio
import logging

from knx_telegram_store import (
    BufferedPostgresStore,
    BufferedSqliteStore,
    KnxTelegramStoreException,
)

from homeassistant.core import HomeAssistant

from .const import KNX_MODULE_KEY, KNX_TELEGRAM_BACKEND_SQLITE

_LOGGER = logging.getLogger(__name__)

# Bounds the wait for a running eviction or VACUUM to finish before the lock is taken
LOCK_TIMEOUT = 30


def _sqlite_store(
    hass: HomeAssistant,
) -> BufferedSqliteStore | BufferedPostgresStore | None:
    """Return the telegram store whose file is part of the backup, if any."""
    if (knx_module := hass.data.get(KNX_MODULE_KEY)) is None:
        return None
    telegrams = knx_module.telegrams
    if telegrams.backend != KNX_TELEGRAM_BACKEND_SQLITE:
        return None
    return telegrams.store


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Checkpoint the telegram database and hold off writes while it is copied."""
    if (store := _sqlite_store(hass)) is None:
        return
    try:
        async with asyncio.timeout(LOCK_TIMEOUT):
            await store.begin_backup()
    except (KnxTelegramStoreException, TimeoutError) as err:
        _LOGGER.warning(
            "Could not prepare the KNX telegram database for the backup, "
            "its copy may be inconsistent: %s",
            err,
        )


async def async_post_backup(hass: HomeAssistant) -> None:
    """Resume writing to the telegram database."""
    if (store := _sqlite_store(hass)) is None:
        return
    try:
        await store.end_backup()
    except KnxTelegramStoreException as err:
        # pre-backup did not take the lock, or the store was replaced meanwhile
        _LOGGER.debug("KNX telegram database was not locked for the backup: %s", err)
