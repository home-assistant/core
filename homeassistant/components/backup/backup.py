"""Local backup support for Core and Container installations."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
import json
from pathlib import Path
from tarfile import TarError
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.hassio import is_hassio

from .agent import BackupAgent, LocalBackupAgent
from .const import DOMAIN, LOGGER
from .models import AgentBackup, BackupNotFound
from .util import read_backup, suggested_filename


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return the local backup agent."""
    if is_hassio(hass):
        return []
    return [CoreLocalBackupAgent(hass)]


class CoreLocalBackupAgent(LocalBackupAgent):
    """Local backup agent for Core and Container installations."""

    domain = DOMAIN
    name = "local"
    unique_id = "local"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self._hass = hass
        self._backup_dir = Path(hass.config.path("backups"))
        self._backups: dict[str, tuple[AgentBackup, Path]] = {}
        self._loaded_backups = False

    async def _load_backups(self) -> None:
        """Load data of stored backup files."""
        backups = await self._hass.async_add_executor_job(self._read_backups)
        LOGGER.debug("Loaded %s local backups", len(backups))
        self._backups = backups
        self._loaded_backups = True

    def _read_backups(self) -> dict[str, tuple[AgentBackup, Path]]:
        """Read backups from disk."""
        backups: dict[str, tuple[AgentBackup, Path]] = {}
        for backup_path in self._backup_dir.glob("*.tar"):
            try:
                backup = read_backup(backup_path)
                backups[backup.backup_id] = (backup, backup_path)
            except (OSError, TarError, json.JSONDecodeError, KeyError) as err:
                LOGGER.warning("Unable to read backup %s: %s", backup_path, err)
        return backups

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        raise NotImplementedError

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        self._backups[backup.backup_id] = (backup, self.get_new_backup_path(backup))

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        if not self._loaded_backups:
            await self._load_backups()
        return [backup for backup, _ in self._backups.values()]

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        if not self._loaded_backups:
            await self._load_backups()

        if backup_id not in self._backups:
            raise BackupNotFound(f"Backup {backup_id} not found")

        backup, backup_path = self._backups[backup_id]
        if not await self._hass.async_add_executor_job(backup_path.exists):
            LOGGER.debug(
                (
                    "Removing tracked backup (%s) that does not exists on the expected"
                    " path %s"
                ),
                backup.backup_id,
                backup_path,
            )
            self._backups.pop(backup_id)
            raise BackupNotFound(f"Backup {backup_id} not found")

        return backup

    def get_backup_path(self, backup_id: str) -> Path:
        """Return the local path to an existing backup.

        Raises BackupAgentError if the backup does not exist.
        """
        try:
            return self._backups[backup_id][1]
        except KeyError as err:
            raise BackupNotFound(f"Backup {backup_id} does not exist") from err

    def get_new_backup_path(self, backup: AgentBackup) -> Path:
        """Return the local path to a new backup."""
        return self._backup_dir / suggested_filename(backup)

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup file."""
        if not self._loaded_backups:
            await self._load_backups()

        backup_path = self.get_backup_path(backup_id)
        await self._hass.async_add_executor_job(backup_path.unlink, True)
        LOGGER.debug("Deleted backup located at %s", backup_path)
        self._backups.pop(backup_id)
