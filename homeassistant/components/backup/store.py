"""Store backup configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

if TYPE_CHECKING:
    from .config import StoredBackupConfig
    from .manager import BackupManager, StoredKnownBackup

STORE_DELAY_SAVE = 30
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 2


class StoredBackupData(TypedDict):
    """Represent the stored backup config."""

    backups: list[StoredKnownBackup]
    config: StoredBackupConfig


class _BackupStore(Store[StoredBackupData]):
    """Class to help storing backup data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize storage class."""
        super().__init__(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_VERSION_MINOR,
        )

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        data = old_data
        if old_major_version == 1:
            if old_minor_version < 2:
                # Version 1.2 adds configurable backup time
                data["config"]["schedule"]["time"] = None

        if old_major_version > 1:
            raise NotImplementedError
        return data


class BackupStore:
    """Store backup config."""

    def __init__(self, hass: HomeAssistant, manager: BackupManager) -> None:
        """Initialize the backup store."""
        self._hass = hass
        self._manager = manager
        self._store = _BackupStore(hass)

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
