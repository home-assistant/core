"""Local backup support for Core and Container installations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tarfile
from tarfile import TarError
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.util.json import json_loads_object

from .agent import BackupAgent, UploadedBackup
from .const import BUF_SIZE, LOGGER
from .models import BackupUploadMetadata


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Register the backup agent."""
    return [LocalBackupAgent(hass)]


@dataclass(slots=True)
class LocalBackup(UploadedBackup):
    """Local backup class."""

    path: Path

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return {**asdict(self), "path": self.path.as_posix()}


class LocalBackupAgent(BackupAgent):
    """Local backup agent for Core and Container installations."""

    name = "local"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self._hass = hass
        self.backup_dir = Path(hass.config.path("backups"))
        self.backups: dict[str, LocalBackup] = {}
        self.loaded_backups = False

    async def load_backups(self) -> None:
        """Load data of stored backup files."""
        backups = await self._hass.async_add_executor_job(self._read_backups)
        LOGGER.debug("Loaded %s local backups", len(backups))
        self.backups = backups
        self.loaded_backups = True

    def _read_backups(self) -> dict[str, LocalBackup]:
        """Read backups from disk."""
        backups: dict[str, LocalBackup] = {}
        for backup_path in self.backup_dir.glob("*.tar"):
            try:
                with tarfile.open(backup_path, "r:", bufsize=BUF_SIZE) as backup_file:
                    if data_file := backup_file.extractfile("./backup.json"):
                        data = json_loads_object(data_file.read())
                        backup = LocalBackup(
                            id=cast(str, data["slug"]),  # Do we need another ID?
                            slug=cast(str, data["slug"]),
                            name=cast(str, data["name"]),
                            date=cast(str, data["date"]),
                            path=backup_path,
                            size=round(backup_path.stat().st_size / 1_048_576, 2),
                            protected=cast(bool, data.get("protected", False)),
                        )
                        backups[backup.slug] = backup
            except (OSError, TarError, json.JSONDecodeError, KeyError) as err:
                LOGGER.warning("Unable to read backup %s: %s", backup_path, err)
        return backups

    async def async_download_backup(
        self,
        *,
        id: str,
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
        self.backups[metadata.slug] = LocalBackup(
            id=metadata.slug,  # Do we need another ID?
            slug=metadata.slug,
            name=metadata.name,
            date=metadata.date,
            path=path,
            size=round(path.stat().st_size / 1_048_576, 2),
            protected=metadata.protected,
        )

    async def async_list_backups(self, **kwargs: Any) -> list[UploadedBackup]:
        """List backups."""
        if not self.loaded_backups:
            await self.load_backups()
        return list(self.backups.values())

    async def async_get_backup(
        self, *, slug: str, **kwargs: Any
    ) -> UploadedBackup | None:
        """Return a backup."""
        if not self.loaded_backups:
            await self.load_backups()

        if not (backup := self.backups.get(slug)):
            return None

        if not backup.path.exists():
            LOGGER.debug(
                (
                    "Removing tracked backup (%s) that does not exists on the expected"
                    " path %s"
                ),
                backup.slug,
                backup.path,
            )
            self.backups.pop(slug)
            return None

        return backup

    def get_backup_path(self, slug: str) -> Path:
        """Return the local path to a backup."""
        return self.backup_dir / f"{slug}.tar"

    async def async_remove_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Remove a backup."""
        if (backup := await self.async_get_backup(slug=slug)) is None:
            return

        await self._hass.async_add_executor_job(backup.path.unlink, True)  # type: ignore[attr-defined]
        LOGGER.debug("Removed backup located at %s", backup.path)  # type: ignore[attr-defined]
        self.backups.pop(slug)
