"""Backup manager for the Backup integration."""

from __future__ import annotations

import abc
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
from queue import SimpleQueue
import shutil
import tarfile
from tempfile import TemporaryDirectory
import time
from typing import Any, Generic, Protocol, cast

import aiohttp
from securetar import SecureTarFile, atomic_contents_add
from typing_extensions import TypeVar

from homeassistant.backup_restore import RESTORE_BACKUP_FILE, password_to_key
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import integration_platform
from homeassistant.helpers.json import json_bytes
from homeassistant.util import dt as dt_util

from .agent import BackupAgent, BackupAgentPlatformProtocol
from .backup import LocalBackupAgent
from .const import (
    BUF_SIZE,
    DOMAIN,
    EXCLUDE_DATABASE_FROM_BACKUP,
    EXCLUDE_FROM_BACKUP,
    LOGGER,
)
from .models import BackupUploadMetadata, BaseBackup

# pylint: disable=fixme
# TODO: Don't forget to remove this when the implementation is complete


LOCAL_AGENT_ID = f"{DOMAIN}.local"

_BackupT = TypeVar("_BackupT", bound=BaseBackup, default=BaseBackup)


@dataclass(slots=True)
class NewBackup:
    """New backup class."""

    slug: str


@dataclass(slots=True)
class Backup(BaseBackup):
    """Backup class."""

    agent_ids: list[str]


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
        self.platforms: dict[str, BackupPlatformProtocol] = {}
        self.backup_agents: dict[str, BackupAgent] = {}
        self.syncing = False

    async def async_setup(self) -> None:
        """Set up the backup manager."""
        await self.load_platforms()

    @callback
    def _add_platform_pre_post_handler(
        self,
        integration_domain: str,
        platform: BackupPlatformProtocol,
    ) -> None:
        """Add a backup platform."""
        if not hasattr(platform, "async_pre_backup") or not hasattr(
            platform, "async_post_backup"
        ):
            return

        self.platforms[integration_domain] = platform

    async def _async_add_platform_agents(
        self,
        integration_domain: str,
        platform: BackupAgentPlatformProtocol,
    ) -> None:
        """Add a platform to the backup manager."""
        if not hasattr(platform, "async_get_backup_agents"):
            return

        agents = await platform.async_get_backup_agents(self.hass)
        self.backup_agents.update(
            {f"{integration_domain}.{agent.name}": agent for agent in agents}
        )

    async def _add_platform(
        self,
        hass: HomeAssistant,
        integration_domain: str,
        platform: Any,
    ) -> None:
        """Add a backup platform manager."""
        self._add_platform_pre_post_handler(integration_domain, platform)
        await self._async_add_platform_agents(integration_domain, platform)

    async def async_pre_backup_actions(self, **kwargs: Any) -> None:
        """Perform pre backup actions."""
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
        await integration_platform.async_process_integration_platforms(
            self.hass,
            DOMAIN,
            self._add_platform,
            wait_for_platforms=True,
        )
        LOGGER.debug("Loaded %s platforms", len(self.platforms))
        LOGGER.debug("Loaded %s agents", len(self.backup_agents))

    @abc.abstractmethod
    async def async_restore_backup(
        self,
        slug: str,
        *,
        password: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Restore a backup."""

    @abc.abstractmethod
    async def async_create_backup(
        self,
        *,
        addons_included: list[str] | None,
        agent_ids: list[str],
        database_included: bool,
        folders_included: list[str] | None,
        name: str | None,
        on_progress: Callable[[BackupProgress], None] | None,
        password: str | None,
        **kwargs: Any,
    ) -> NewBackup:
        """Initiate generating a backup.

        :param on_progress: A callback that will be called with the progress of the
            backup.
        """

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
    async def async_upload_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Upload a backup."""


class BackupManager(BaseBackupManager[Backup]):
    """Backup manager for the Backup integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup manager."""
        super().__init__(hass=hass)
        self.backup_dir = Path(hass.config.path("backups"))
        self.temp_backup_dir = Path(hass.config.path("tmp_backups"))

    async def async_upload_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Upload a backup to all agents."""
        if not self.backup_agents:
            return

        if not (backup := await self.async_get_backup(slug=slug)):
            return

        local_agent = cast(LocalBackupAgent, self.backup_agents[LOCAL_AGENT_ID])
        await self._async_upload_backup(
            backup=backup,
            agent_ids=list(self.backup_agents.keys()),
            # TODO: This should be the path to the backup file
            path=local_agent.get_backup_path(slug),
        )

    async def _async_upload_backup(
        self,
        *,
        backup: Backup,
        agent_ids: list[str],
        path: Path,
    ) -> None:
        """Upload a backup to selected agents."""
        self.syncing = True
        sync_backup_results = await asyncio.gather(
            *(
                self.backup_agents[agent_id].async_upload_backup(
                    path=path,
                    metadata=BackupUploadMetadata(
                        homeassistant=HAVERSION,
                        size=backup.size,
                        date=backup.date,
                        slug=backup.slug,
                        name=backup.name,
                        protected=backup.protected,
                    ),
                )
                for agent_id in agent_ids
            ),
            return_exceptions=True,
        )
        for result in sync_backup_results:
            if isinstance(result, Exception):
                LOGGER.error("Error during backup upload - %s", result)
        # TODO: Reset self.syncing in a finally block
        self.syncing = False

    async def async_get_backups(self, **kwargs: Any) -> dict[str, Backup]:
        """Return backups."""
        backups: dict[str, Backup] = {}
        for agent_id, agent in self.backup_agents.items():
            agent_backups = await agent.async_list_backups()
            for agent_backup in agent_backups:
                if agent_backup.slug not in backups:
                    backups[agent_backup.slug] = Backup(
                        slug=agent_backup.slug,
                        name=agent_backup.name,
                        date=agent_backup.date,
                        agent_ids=[],
                        size=agent_backup.size,
                        protected=agent_backup.protected,
                    )
                backups[agent_backup.slug].agent_ids.append(agent_id)

        return backups

    async def async_get_backup(self, *, slug: str, **kwargs: Any) -> Backup | None:
        """Return a backup."""
        # TODO: This is not efficient, but it's fine for draft
        backups = await self.async_get_backups()
        return backups.get(slug)

    async def async_get_backup_path(self, *, slug: str, **kwargs: Any) -> Path | None:
        """Return path to a backup which is available locally."""
        local_agent = cast(LocalBackupAgent, self.backup_agents[LOCAL_AGENT_ID])
        if not await local_agent.async_get_backup(slug=slug):
            return None
        return local_agent.get_backup_path(slug)

    async def async_remove_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Remove a backup."""
        # TODO: We should only remove from the agents that have the backup
        for agent in self.backup_agents.values():
            await agent.async_remove_backup(slug=slug)  # type: ignore[attr-defined]

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
        # TODO: What do we need to do instead?

    async def async_create_backup(
        self,
        *,
        addons_included: list[str] | None,
        agent_ids: list[str],
        database_included: bool,
        folders_included: list[str] | None,
        name: str | None,
        on_progress: Callable[[BackupProgress], None] | None,
        password: str | None,
        **kwargs: Any,
    ) -> NewBackup:
        """Initiate generating a backup."""
        if self.backup_task:
            raise HomeAssistantError("Backup already in progress")
        if not agent_ids:
            raise HomeAssistantError("At least one agent must be selected")
        if any(agent_id not in self.backup_agents for agent_id in agent_ids):
            raise HomeAssistantError("Invalid agent selected")
        backup_name = name or f"Core {HAVERSION}"
        date_str = dt_util.now().isoformat()
        slug = _generate_slug(date_str, backup_name)
        self.backup_task = self.hass.async_create_task(
            self._async_create_backup(
                addons_included=addons_included,
                agent_ids=agent_ids,
                backup_name=backup_name,
                database_included=database_included,
                date_str=date_str,
                folders_included=folders_included,
                on_progress=on_progress,
                password=password,
                slug=slug,
            ),
            name="backup_manager_create_backup",
            eager_start=False,  # To ensure the task is not started before we return
        )
        return NewBackup(slug=slug)

    async def _async_create_backup(
        self,
        *,
        addons_included: list[str] | None,
        agent_ids: list[str],
        database_included: bool,
        backup_name: str,
        date_str: str,
        folders_included: list[str] | None,
        on_progress: Callable[[BackupProgress], None] | None,
        password: str | None,
        slug: str,
    ) -> Backup:
        """Generate a backup."""
        success = False

        if LOCAL_AGENT_ID in agent_ids:
            local_agent = cast(LocalBackupAgent, self.backup_agents[LOCAL_AGENT_ID])
            tar_file_path = local_agent.get_backup_path(slug)
        else:
            tar_file_path = self.temp_backup_dir / f"{slug}.tar"

        try:
            await self.async_pre_backup_actions()

            backup_data = {
                "slug": slug,
                "name": backup_name,
                "date": date_str,
                "type": "partial",
                "folders": ["homeassistant"],
                "homeassistant": {
                    "exclude_database": not database_included,
                    "version": HAVERSION,
                },
                "compressed": True,
                "protected": password is not None,
            }

            size_in_bytes = await self.hass.async_add_executor_job(
                self._mkdir_and_generate_backup_contents,
                tar_file_path,
                backup_data,
                database_included,
                password,
            )
            backup = Backup(
                slug=slug,
                name=backup_name,
                date=date_str,
                size=round(size_in_bytes / 1_048_576, 2),
                protected=password is not None,
                agent_ids=agent_ids,  # TODO: This should maybe be set after upload
            )
            # TODO: We should add a cache of the backup metadata
            LOGGER.debug(
                "Generated new backup with slug %s, uploading to agents %s",
                slug,
                agent_ids,
            )
            await self._async_upload_backup(
                backup=backup, agent_ids=agent_ids, path=tar_file_path
            )
            if LOCAL_AGENT_ID not in agent_ids:
                tar_file_path.unlink(True)
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
        database_included: bool,
        password: str | None,
    ) -> int:
        """Generate backup contents and return the size."""
        if not (backup_dir := tar_file_path.parent).exists():
            LOGGER.debug("Creating backup directory %s", backup_dir)
            backup_dir.mkdir()

        excludes = EXCLUDE_FROM_BACKUP
        if not database_included:
            excludes = excludes + EXCLUDE_DATABASE_FROM_BACKUP

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
                "./homeassistant.tar.gz",
                gzip=True,
                key=password_to_key(password) if password is not None else None,
            ) as core_tar:
                atomic_contents_add(
                    tar_file=core_tar,
                    origin_path=Path(self.hass.config.path()),
                    excludes=excludes,
                    arcname="data",
                )
        return tar_file_path.stat().st_size

    async def async_restore_backup(
        self,
        slug: str,
        *,
        password: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Restore a backup.

        This will write the restore information to .HA_RESTORE which
        will be handled during startup by the restore_backup module.
        """
        if (backup := await self.async_get_backup(slug=slug)) is None:
            raise HomeAssistantError(f"Backup {slug} not found")

        def _write_restore_file() -> None:
            """Write the restore file."""
            Path(self.hass.config.path(RESTORE_BACKUP_FILE)).write_text(
                json.dumps({"path": backup.path.as_posix(), "password": password}),  # type: ignore[attr-defined]
                encoding="utf-8",
            )

        await self.hass.async_add_executor_job(_write_restore_file)
        await self.hass.services.async_call("homeassistant", "restart", {})


def _generate_slug(date: str, name: str) -> str:
    """Generate a backup slug."""
    return hashlib.sha1(f"{date} - {name}".lower().encode()).hexdigest()[:8]
