"""Local backup support for Core and Container installations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from tarfile import TarError
from typing import Any

from homeassistant.core import HomeAssistant

from .agent import BackupAgent, LocalBackupAgent
from .const import LOGGER
from .models import BackupUploadMetadata, BaseBackup
from .util import read_backup


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return the local backup agent."""
    return [CoreLocalBackupAgent(hass)]


@dataclass(slots=True)
class LocalBackup(BaseBackup):
    """Local backup class."""

    path: Path

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return {**asdict(self), "path": self.path.as_posix()}


class CoreLocalBackupAgent(LocalBackupAgent):
    """Local backup agent for Core and Container installations."""

    name = "local"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self._hass = hass
        self._backup_dir = Path(hass.config.path("backups"))
        self._backups: dict[str, LocalBackup] = {}
        self._loaded_backups = False

    async def load_backups(self) -> None:
        """Load data of stored backup files."""
        backups = await self._hass.async_add_executor_job(self._read_backups)
        LOGGER.debug("Loaded %s local backups", len(backups))
        self._backups = backups
        self._loaded_backups = True

    def _read_backups(self) -> dict[str, LocalBackup]:
        """Read backups from disk."""
        backups: dict[str, LocalBackup] = {}
        for backup_path in self._backup_dir.glob("*.tar"):
            try:
                base_backup = read_backup(backup_path)
                backup = LocalBackup(
                    backup_id=base_backup.backup_id,
                    name=base_backup.name,
                    date=base_backup.date,
                    path=backup_path,
                    size=round(backup_path.stat().st_size / 1_048_576, 2),
                    protected=base_backup.protected,
                )
                backups[backup.backup_id] = backup
            except (OSError, TarError, json.JSONDecodeError, KeyError) as err:
                LOGGER.warning("Unable to read backup %s: %s", backup_path, err)
        return backups

    async def async_download_backup(
        self,
        backup_id: str,
        *,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file."""
        raise NotImplementedError

    async def async_upload_backup(
        self,
        *,
        path: Path,
        metadata: BackupUploadMetadata,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        self._backups[metadata.backup_id] = LocalBackup(
            backup_id=metadata.backup_id,
            date=metadata.date,
            name=metadata.name,
            path=path,
            protected=metadata.protected,
            size=round(path.stat().st_size / 1_048_576, 2),
        )

    async def async_list_backups(self, **kwargs: Any) -> list[BaseBackup]:
        """List backups."""
        if not self._loaded_backups:
            await self.load_backups()
        return list(self._backups.values())

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> LocalBackup | None:
        """Return a backup."""
        if not self._loaded_backups:
            await self.load_backups()

        if not (backup := self._backups.get(backup_id)):
            return None

        if not await self._hass.async_add_executor_job(backup.path.exists):
            LOGGER.debug(
                (
                    "Removing tracked backup (%s) that does not exists on the expected"
                    " path %s"
                ),
                backup.backup_id,
                backup.path,
            )
            self._backups.pop(backup_id)
            return None

        return backup

    def get_backup_path(self, backup_id: str) -> Path:
        """Return the local path to a backup."""
        return self._backup_dir / f"{backup_id}.tar"

    async def async_remove_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Remove a backup."""
        if (backup := await self.async_get_backup(backup_id)) is None:
            return

        await self._hass.async_add_executor_job(backup.path.unlink, True)
        LOGGER.debug("Removed backup located at %s", backup.path)
        self._backups.pop(backup_id)
