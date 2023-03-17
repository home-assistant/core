"""Backup manager for the Backup integration."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import tarfile
from tarfile import TarError
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from securetar import SecureTarFile, atomic_contents_add

from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import integration_platform
from homeassistant.helpers.json import save_json
from homeassistant.util import dt

from .const import DOMAIN, EXCLUDE_FROM_BACKUP, LOGGER


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
        return {**asdict(self), "path": self.path.as_posix()}


class BackupPlatformProtocol(Protocol):
    """Define the format that backup platforms can have."""

    async def async_pre_backup(self, hass: HomeAssistant) -> None:
        """Perform operations before a backup starts."""

    async def async_post_backup(self, hass: HomeAssistant) -> None:
        """Perform operations after a backup finishes."""


class BackupManager:
    """Backup manager for the Backup integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup manager."""
        self.hass = hass
        self.backup_dir = Path(hass.config.path("backups"))
        self.backing_up = False
        self.backups: dict[str, Backup] = {}
        self.platforms: dict[str, BackupPlatformProtocol] = {}
        self.loaded_backups = False
        self.loaded_platforms = False

    async def _add_platform(
        self,
        hass: HomeAssistant,
        integration_domain: str,
        platform: BackupPlatformProtocol,
    ) -> None:
        """Add a platform to the backup manager."""
        if not hasattr(platform, "async_pre_backup") or not hasattr(
            platform, "async_post_backup"
        ):
            LOGGER.warning(
                "%s does not implement required functions for the backup platform",
                integration_domain,
            )
            return
        self.platforms[integration_domain] = platform

    async def load_backups(self) -> None:
        """Load data of stored backup files."""
        backups = await self.hass.async_add_executor_job(self._read_backups)
        LOGGER.debug("Loaded %s backups", len(backups))
        self.backups = backups
        self.loaded_backups = True

    async def load_platforms(self) -> None:
        """Load backup platforms."""
        await integration_platform.async_process_integration_platforms(
            self.hass, DOMAIN, self._add_platform
        )
        LOGGER.debug("Loaded %s platforms", len(self.platforms))
        self.loaded_platforms = True

    def _read_backups(self) -> dict[str, Backup]:
        """Read backups from disk."""
        backups: dict[str, Backup] = {}
        for backup_path in self.backup_dir.glob("*.tar"):
            try:
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
            except (OSError, TarError, json.JSONDecodeError, KeyError) as err:
                LOGGER.warning("Unable to read backup %s: %s", backup_path, err)
        return backups

    async def get_backups(self) -> dict[str, Backup]:
        """Return backups."""
        if not self.loaded_backups:
            await self.load_backups()

        return self.backups

    async def get_backup(self, slug: str) -> Backup | None:
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

    async def remove_backup(self, slug: str) -> None:
        """Remove a backup."""
        if (backup := await self.get_backup(slug)) is None:
            return

        await self.hass.async_add_executor_job(backup.path.unlink, True)
        LOGGER.debug("Removed backup located at %s", backup.path)
        self.backups.pop(slug)

    async def generate_backup(self) -> Backup:
        """Generate a backup."""
        if self.backing_up:
            raise HomeAssistantError("Backup already in progress")

        if not self.loaded_platforms:
            await self.load_platforms()

        try:
            self.backing_up = True
            pre_backup_results = await asyncio.gather(
                *(
                    platform.async_pre_backup(self.hass)
                    for platform in self.platforms.values()
                ),
                return_exceptions=True,
            )
            for result in pre_backup_results:
                if isinstance(result, Exception):
                    raise result

            backup_name = f"Core {HAVERSION}"
            date_str = dt.now().isoformat()
            slug = _generate_slug(date_str, backup_name)

            backup_data = {
                "slug": slug,
                "name": backup_name,
                "date": date_str,
                "type": "partial",
                "folders": ["homeassistant"],
                "homeassistant": {"version": HAVERSION},
                "compressed": True,
            }
            tar_file_path = Path(self.backup_dir, f"{backup_data['slug']}.tar")

            if not self.backup_dir.exists():
                LOGGER.debug("Creating backup directory")
                self.hass.async_add_executor_job(self.backup_dir.mkdir)

            await self.hass.async_add_executor_job(
                self._generate_backup_contents,
                tar_file_path,
                backup_data,
            )
            backup = Backup(
                slug=slug,
                name=backup_name,
                date=date_str,
                path=tar_file_path,
                size=round(tar_file_path.stat().st_size / 1_048_576, 2),
            )
            if self.loaded_backups:
                self.backups[slug] = backup
            LOGGER.debug("Generated new backup with slug %s", slug)
            return backup
        finally:
            self.backing_up = False
            post_backup_results = await asyncio.gather(
                *(
                    platform.async_post_backup(self.hass)
                    for platform in self.platforms.values()
                ),
                return_exceptions=True,
            )
            for result in post_backup_results:
                if isinstance(result, Exception):
                    raise result

    def _generate_backup_contents(
        self,
        tar_file_path: Path,
        backup_data: dict[str, Any],
    ) -> None:
        """Generate backup contents."""
        with TemporaryDirectory() as tmp_dir, SecureTarFile(
            tar_file_path, "w", gzip=False
        ) as tar_file:
            tmp_dir_path = Path(tmp_dir)
            save_json(
                tmp_dir_path.joinpath("./backup.json").as_posix(),
                backup_data,
            )
            with SecureTarFile(
                tmp_dir_path.joinpath("./homeassistant.tar.gz").as_posix(),
                "w",
            ) as core_tar:
                atomic_contents_add(
                    tar_file=core_tar,
                    origin_path=Path(self.hass.config.path()),
                    excludes=EXCLUDE_FROM_BACKUP,
                    arcname="data",
                )
            tar_file.add(tmp_dir_path, arcname=".")


def _generate_slug(date: str, name: str) -> str:
    """Generate a backup slug."""
    return hashlib.sha1(f"{date} - {name}".lower().encode()).hexdigest()[:8]
