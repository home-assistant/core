"""Backup manager for the Backup integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory

from awesomeversion import AwesomeVersion

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import json as json_util
from homeassistant.util.dt import now

from .const import EXCLUDE_FROM_BACKUP, HA_VERSION_OBJ, LOGGER


@dataclass
class Backup:
    """Backup class."""

    slug: str
    name: str
    date: str
    path: Path
    size: float

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return {
            "slug": self.slug,
            "name": self.name,
            "date": self.date,
            "size": self.size,
            "path": self.path.as_posix(),
        }


class BackupManager:
    """Backup manager for the Backup integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup manager."""
        self._backups: dict[str, Backup] = {}
        self.hass = hass
        self.backup_dir = Path(hass.config.path("backups"))
        self.backing_up = False

    @property
    def backups(self) -> dict[str, Backup]:
        """Return a dict of backups."""
        return self._backups

    async def load_backups(self) -> None:
        """Load data of stored backup files."""
        backups = {}

        def _read_backup_info(backup_path: Path) -> None:
            with tarfile.open(backup_path, "r:") as backup_file:
                if data_file := backup_file.extractfile("./backup.json"):
                    data = json.loads(data_file.read())
                    backup = Backup(
                        slug=data["slug"],
                        name=data["name"],
                        date=data["date"],
                        path=backup_path,
                        size=round(backup_path.stat().st_size / 1_048_576, 2),
                    )
                    backups[backup.slug] = backup

        await asyncio.gather(
            *[
                self.hass.async_add_executor_job(_read_backup_info, backup)
                for backup in self.backup_dir.glob("*.tar")
            ]
        )

        LOGGER.info("Loaded %s backups", len(backups.values()))
        self._backups = backups

    def get_backup(self, slug: str) -> Backup | None:
        """Return a backup."""
        return self._backups.get(slug)

    def remove_backup(self, slug: str) -> None:
        """Remove a backup."""
        if (backup := self.get_backup(slug)) is None:
            return
        backup.path.unlink(missing_ok=True)
        LOGGER.info("Removed backup located at %s", backup.path)
        self._backups.pop(slug, None)

    async def generate_backup(self) -> str:
        """Generate a backup."""
        if self.backing_up:
            raise HomeAssistantError("Backup in progress")

        self.backing_up = True
        backup_name = f"Core {HA_VERSION_OBJ}"
        date_str = now().isoformat()
        slug = _generate_slug(date_str, backup_name)

        def _create_backup() -> None:
            with TemporaryDirectory() as tmp_dir:
                tar_file = Path(self.backup_dir, f"{slug}.tar")

                json_util.save_json(
                    Path(tmp_dir, "backup.json").as_posix(),
                    _generate_backup_data(slug, backup_name, date_str, HA_VERSION_OBJ),
                )

                with tarfile.open(Path(tmp_dir, "homeassistant.tar.gz"), "w:gz") as tar:
                    _add_directory_to_tarfile(
                        tar_file=tar,
                        origin_path=Path(self.hass.config.path()),
                    )

                with tarfile.open(tar_file, "w:") as tar:
                    tar.add(tmp_dir, arcname=".")

        await self.hass.async_add_executor_job(_create_backup)
        await self.load_backups()
        self.backing_up = False
        LOGGER.info("Generated new backup with slug %s", slug)

        return slug


def _add_directory_to_tarfile(
    tar_file: tarfile.TarFile,
    origin_path: Path,
    arcname: str = ".",
) -> None:
    """Add a directory to a tarfile."""

    def _is_excluded_by_filter(path: Path) -> bool:
        for exclude in EXCLUDE_FROM_BACKUP:
            if path.match(exclude):
                return True
        return False

    for directory_item in origin_path.iterdir():
        if _is_excluded_by_filter(directory_item):
            continue

        arcpath = Path(arcname, directory_item.name).as_posix()
        if directory_item.is_dir() and not directory_item.is_symlink():
            _add_directory_to_tarfile(tar_file, directory_item, arcpath)
            continue

        tar_file.add(directory_item.as_posix(), arcname=arcpath, recursive=False)


def _generate_slug(date: str, name: str) -> str:
    """Generate a backup slug."""
    return hashlib.sha1(f"{date} - {name}".lower().encode()).hexdigest()[:8]


def _generate_backup_data(
    slug: str,
    name: str,
    date: str,
    version: AwesomeVersion,
) -> dict:
    """Generate a backup data."""
    data = {
        "slug": slug,
        "name": name,
        "date": date,
        "type": "partial",
        "folders": ["homeassistant"],
        "homeassistant": {},
        "compressed": True,
    }
    if not version.dev:
        data["homeassistant"] = {"version": version}
    return data
