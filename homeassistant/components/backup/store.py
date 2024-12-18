"""Store backup configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

if TYPE_CHECKING:
    from .config import StoredBackupConfig
    from .manager import BackupManager, StoredKnownBackup

STORE_DELAY_SAVE = 30
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


class StoredBackupData(TypedDict):
    """Represent the stored backup config."""

    backups: list[StoredKnownBackup]
    config: StoredBackupConfig


class BackupStore:
    """Store backup config."""

    def __init__(self, hass: HomeAssistant, manager: BackupManager) -> None:
        """Initialize the backup manager."""
        self._hass = hass
        self._manager = manager
        self._store: Store[StoredBackupData] = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def load(self) -> StoredBackupData | None:
        """Load the store."""
        return await self._store.async_load()

    @callback
    def save(self) -> None:
        """Save config."""
        self._store.async_delay_save(self._data_to_save, STORE_DELAY_SAVE)

    @callback
    def _data_to_save(self) -> StoredBackupData:
        """Return data to save."""
        return {
            "backups": self._manager.known_backups.to_list(),
            "config": self._manager.config.data.to_dict(),
        }
