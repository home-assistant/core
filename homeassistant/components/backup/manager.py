"""Backup manager for the Backup integration."""

from __future__ import annotations

import abc
import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
import hashlib
import io
import json
from pathlib import Path
from queue import SimpleQueue
import shutil
import tarfile
from tarfile import TarError
from tempfile import TemporaryDirectory
import time
from typing import Any, Generic, Protocol, cast

import aiohttp
from securetar import SecureTarFile, atomic_contents_add
from typing_extensions import TypeVar

from homeassistant.backup_restore import RESTORE_BACKUP_FILE
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import integration_platform
from homeassistant.helpers.json import json_bytes
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object

from .const import DOMAIN, EXCLUDE_FROM_BACKUP, LOGGER
from .models import BaseBackup
from .sync_agent import BackupPlatformAgentProtocol, BackupSyncAgent

BUF_SIZE = 2**20 * 4  # 4MB

_BackupT = TypeVar("_BackupT", bound=BaseBackup, default=BaseBackup)


@dataclass(slots=True)
class NewBackup:
    """New backup class."""

    slug: str


@dataclass(slots=True)
class Backup(BaseBackup):
    """Backup class."""

    path: Path

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return {**asdict(self), "path": self.path.as_posix()}


@dataclass(slots=True)
class BackupProgress:
    """Backup progress class."""

    done: bool
    stage: str | None
    success: bool | None


class BackupPlatformProtocol(Protocol):
    """Define the format that backup platforms can have."""

    async def async_pre_backup(self, hass: HomeAssistant) -> None:
        """Perform operations before a backup starts."""

    async def async_post_backup(self, hass: HomeAssistant) -> None:
        """Perform operations after a backup finishes."""


class BaseBackupManager(abc.ABC, Generic[_BackupT]):
    """Define the format that backup managers can have."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup manager."""
        self.hass = hass
        self.backup_task: asyncio.Task | None = None
        self.backups: dict[str, _BackupT] = {}
        self.loaded_platforms = False
        self.platforms: dict[str, BackupPlatformProtocol] = {}
        self.sync_agents: dict[str, BackupSyncAgent] = {}
        self.syncing = False

    @callback
    def _add_platform_pre_post_handlers(
        self,
        hass: HomeAssistant,
        integration_domain: str,
        platform: BackupPlatformProtocol,
    ) -> None:
        """Add a platform to the backup manager."""
        if not hasattr(platform, "async_pre_backup") or not hasattr(
            platform, "async_post_backup"
        ):
            return

        self.platforms[integration_domain] = platform

    async def _async_add_platform_agents(
        self,
        hass: HomeAssistant,
        integration_domain: str,
        platform: BackupPlatformAgentProtocol,
    ) -> None:
        """Add a platform to the backup manager."""
        if not hasattr(platform, "async_get_backup_sync_agents"):
            return

        agents = await platform.async_get_backup_sync_agents(hass=hass)
        self.sync_agents.update(
            {f"{integration_domain}.{agent.name}": agent for agent in agents}
        )

    async def async_pre_backup_actions(self, **kwargs: Any) -> None:
        """Perform pre backup actions."""
        if not self.loaded_platforms:
            await self.load_platforms()

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

    async def async_post_backup_actions(self, **kwargs: Any) -> None:
        """Perform post backup actions."""
        if not self.loaded_platforms:
            await self.load_platforms()

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

    async def load_platforms(self) -> None:
        """Load backup platforms."""
        if self.loaded_platforms:
            return
        await integration_platform.async_process_integration_platforms(
            self.hass,
            DOMAIN,
            self._add_platform_pre_post_handlers,
            wait_for_platforms=True,
        )
        await integration_platform.async_process_integration_platforms(
            self.hass,
            DOMAIN,
            self._async_add_platform_agents,
            wait_for_platforms=True,
        )
        LOGGER.debug("Loaded %s platforms", len(self.platforms))
        LOGGER.debug("Loaded %s agents", len(self.sync_agents))
        self.loaded_platforms = True

    @abc.abstractmethod
    async def async_restore_backup(self, slug: str, **kwargs: Any) -> None:
        """Restore a backup."""

    @abc.abstractmethod
    async def async_create_backup(
        self,
        *,
        on_progress: Callable[[BackupProgress], None] | None,
        **kwargs: Any,
    ) -> NewBackup:
        """Generate a backup."""

    @abc.abstractmethod
    async def async_get_backups(self, **kwargs: Any) -> dict[str, _BackupT]:
        """Get backups.

        Return a dictionary of Backup instances keyed by their slug.
        """

    @abc.abstractmethod
    async def async_get_backup(self, *, slug: str, **kwargs: Any) -> _BackupT | None:
        """Get a backup."""

    @abc.abstractmethod
    async def async_remove_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Remove a backup."""

    @abc.abstractmethod
    async def async_receive_backup(
        self,
        *,
        contents: aiohttp.BodyPartReader,
        **kwargs: Any,
    ) -> None:
        """Receive and store a backup file from upload."""

    @abc.abstractmethod
    async def async_sync_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Sync a backup."""


class BackupManager(BaseBackupManager[Backup]):
    """Backup manager for the Backup integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup manager."""
        super().__init__(hass=hass)
        self.backup_dir = Path(hass.config.path("backups"))
        self.loaded_backups = False

    async def async_sync_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Sync a backup."""
        await self.load_platforms()

        if not self.sync_agents:
            return

        if not (backup := await self.async_get_backup(slug=slug)):
            return

        self.syncing = True
        sync_backup_results = await asyncio.gather(
            *(
                agent.async_upload_backup(
                    path=backup.path,
                    metadata={
                        "homeassistant": HAVERSION,
                        "size": backup.size,
                        "date": backup.date,
                        "slug": backup.slug,
                        "name": backup.name,
                    },
                )
                for agent in self.sync_agents.values()
            ),
            return_exceptions=True,
        )
        for result in sync_backup_results:
            if isinstance(result, Exception):
                LOGGER.error("Error during backup sync - %s", result)
        self.syncing = False

    async def load_backups(self) -> None:
        """Load data of stored backup files."""
        backups = await self.hass.async_add_executor_job(self._read_backups)
        LOGGER.debug("Loaded %s local backups", len(backups))
        self.backups = backups
        self.loaded_backups = True

    def _read_backups(self) -> dict[str, Backup]:
        """Read backups from disk."""
        backups: dict[str, Backup] = {}
        for backup_path in self.backup_dir.glob("*.tar"):
            try:
                with tarfile.open(backup_path, "r:", bufsize=BUF_SIZE) as backup_file:
                    if data_file := backup_file.extractfile("./backup.json"):
                        data = json_loads_object(data_file.read())
                        backup = Backup(
                            slug=cast(str, data["slug"]),
                            name=cast(str, data["name"]),
                            date=cast(str, data["date"]),
                            path=backup_path,
                            size=round(backup_path.stat().st_size / 1_048_576, 2),
                        )
                        backups[backup.slug] = backup
            except (OSError, TarError, json.JSONDecodeError, KeyError) as err:
                LOGGER.warning("Unable to read backup %s: %s", backup_path, err)
        return backups

    async def async_get_backups(self, **kwargs: Any) -> dict[str, Backup]:
        """Return backups."""
        if not self.loaded_backups:
            await self.load_backups()

        return self.backups

    async def async_get_backup(self, *, slug: str, **kwargs: Any) -> Backup | None:
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

    async def async_remove_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Remove a backup."""
        if (backup := await self.async_get_backup(slug=slug)) is None:
            return

        await self.hass.async_add_executor_job(backup.path.unlink, True)
        LOGGER.debug("Removed backup located at %s", backup.path)
        self.backups.pop(slug)

    async def async_receive_backup(
        self,
        *,
        contents: aiohttp.BodyPartReader,
        **kwargs: Any,
    ) -> None:
        """Receive and store a backup file from upload."""
        queue: SimpleQueue[tuple[bytes, asyncio.Future[None] | None] | None] = (
            SimpleQueue()
        )
        temp_dir_handler = await self.hass.async_add_executor_job(TemporaryDirectory)
        target_temp_file = Path(
            temp_dir_handler.name, contents.filename or "backup.tar"
        )

        def _sync_queue_consumer() -> None:
            with target_temp_file.open("wb") as file_handle:
                while True:
                    if (_chunk_future := queue.get()) is None:
                        break
                    _chunk, _future = _chunk_future
                    if _future is not None:
                        self.hass.loop.call_soon_threadsafe(_future.set_result, None)
                    file_handle.write(_chunk)

        fut: asyncio.Future[None] | None = None
        try:
            fut = self.hass.async_add_executor_job(_sync_queue_consumer)
            megabytes_sending = 0
            while chunk := await contents.read_chunk(BUF_SIZE):
                megabytes_sending += 1
                if megabytes_sending % 5 != 0:
                    queue.put_nowait((chunk, None))
                    continue

                chunk_future = self.hass.loop.create_future()
                queue.put_nowait((chunk, chunk_future))
                await asyncio.wait(
                    (fut, chunk_future),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if fut.done():
                    # The executor job failed
                    break

            queue.put_nowait(None)  # terminate queue consumer
        finally:
            if fut is not None:
                await fut

        def _move_and_cleanup() -> None:
            shutil.move(target_temp_file, self.backup_dir / target_temp_file.name)
            temp_dir_handler.cleanup()

        await self.hass.async_add_executor_job(_move_and_cleanup)
        await self.load_backups()

    async def async_create_backup(
        self,
        *,
        on_progress: Callable[[BackupProgress], None] | None,
        **kwargs: Any,
    ) -> NewBackup:
        """Generate a backup."""
        if self.backup_task:
            raise HomeAssistantError("Backup already in progress")
        backup_name = f"Core {HAVERSION}"
        date_str = dt_util.now().isoformat()
        slug = _generate_slug(date_str, backup_name)
        self.backup_task = self.hass.async_create_task(
            self._async_create_backup(backup_name, date_str, slug, on_progress),
            name="backup_manager_create_backup",
            eager_start=False,  # To ensure the task is not started before we return
        )
        return NewBackup(slug=slug)

    async def _async_create_backup(
        self,
        backup_name: str,
        date_str: str,
        slug: str,
        on_progress: Callable[[BackupProgress], None] | None,
    ) -> Backup:
        """Generate a backup."""
        success = False
        try:
            await self.async_pre_backup_actions()

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
            size_in_bytes = await self.hass.async_add_executor_job(
                self._mkdir_and_generate_backup_contents,
                tar_file_path,
                backup_data,
            )
            backup = Backup(
                slug=slug,
                name=backup_name,
                date=date_str,
                path=tar_file_path,
                size=round(size_in_bytes / 1_048_576, 2),
            )
            if self.loaded_backups:
                self.backups[slug] = backup
            LOGGER.debug("Generated new backup with slug %s", slug)
            success = True
            return backup
        finally:
            if on_progress:
                on_progress(BackupProgress(done=True, stage=None, success=success))
            self.backup_task = None
            await self.async_post_backup_actions()

    def _mkdir_and_generate_backup_contents(
        self,
        tar_file_path: Path,
        backup_data: dict[str, Any],
    ) -> int:
        """Generate backup contents and return the size."""
        if not self.backup_dir.exists():
            LOGGER.debug("Creating backup directory")
            self.backup_dir.mkdir()

        outer_secure_tarfile = SecureTarFile(
            tar_file_path, "w", gzip=False, bufsize=BUF_SIZE
        )
        with outer_secure_tarfile as outer_secure_tarfile_tarfile:
            raw_bytes = json_bytes(backup_data)
            fileobj = io.BytesIO(raw_bytes)
            tar_info = tarfile.TarInfo(name="./backup.json")
            tar_info.size = len(raw_bytes)
            tar_info.mtime = int(time.time())
            outer_secure_tarfile_tarfile.addfile(tar_info, fileobj=fileobj)
            with outer_secure_tarfile.create_inner_tar(
                "./homeassistant.tar.gz", gzip=True
            ) as core_tar:
                atomic_contents_add(
                    tar_file=core_tar,
                    origin_path=Path(self.hass.config.path()),
                    excludes=EXCLUDE_FROM_BACKUP,
                    arcname="data",
                )

        return tar_file_path.stat().st_size

    async def async_restore_backup(self, slug: str, **kwargs: Any) -> None:
        """Restore a backup.

        This will write the restore information to .HA_RESTORE which
        will be handled during startup by the restore_backup module.
        """
        if (backup := await self.async_get_backup(slug=slug)) is None:
            raise HomeAssistantError(f"Backup {slug} not found")

        def _write_restore_file() -> None:
            """Write the restore file."""
            Path(self.hass.config.path(RESTORE_BACKUP_FILE)).write_text(
                json.dumps({"path": backup.path.as_posix()}),
                encoding="utf-8",
            )

        await self.hass.async_add_executor_job(_write_restore_file)
        await self.hass.services.async_call("homeassistant", "restart", {})


def _generate_slug(date: str, name: str) -> str:
    """Generate a backup slug."""
    return hashlib.sha1(f"{date} - {name}".lower().encode()).hexdigest()[:8]
