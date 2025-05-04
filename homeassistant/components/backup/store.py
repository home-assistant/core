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
STORAGE_VERSION_MINOR = 7


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
            if old_minor_version < 3:
                # Version 1.2 bumped to 1.3 because 1.2 was changed several
                # times during development.
                # Version 1.3 adds per agent settings, configurable backup time
                # and custom days
                data["config"]["agents"] = {}
                data["config"]["schedule"]["time"] = None
                if (state := data["config"]["schedule"]["state"]) in ("daily", "never"):
                    data["config"]["schedule"]["days"] = []
                    data["config"]["schedule"]["recurrence"] = state
                else:
                    data["config"]["schedule"]["days"] = [state]
                    data["config"]["schedule"]["recurrence"] = "custom_days"
            if old_minor_version < 4:
                # Workaround for a bug in frontend which incorrectly set days to 0
                # instead of to None for unlimited retention.
                if data["config"]["retention"]["copies"] == 0:
                    data["config"]["retention"]["copies"] = None
                if data["config"]["retention"]["days"] == 0:
                    data["config"]["retention"]["days"] = None
            if old_minor_version < 5:
                # Version 1.5 adds automatic_backups_configured
                data["config"]["automatic_backups_configured"] = (
                    data["config"]["create_backup"]["password"] is not None
                )
            if old_minor_version < 6:
                # Version 1.6 adds agent retention settings
                for agent in data["config"]["agents"]:
                    data["config"]["agents"][agent]["retention"] = None
            if old_minor_version < 7:
                # Version 1.7 adds last completed automatic backup id
                data["config"]["last_completed_automatic_backup_id"] = None

        # Note: We allow reading data with major version 2.
        # Reject if major version is higher than 2.
        if old_major_version > 2:
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
