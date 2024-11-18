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
from typing import Any, Generic, Protocol

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

from .agent import (
    BackupAgent,
    BackupAgentError,
    BackupAgentPlatformProtocol,
    LocalBackupAgent,
)
from .config import BackupConfig
from .const import (
    BUF_SIZE,
    DOMAIN,
    EXCLUDE_DATABASE_FROM_BACKUP,
    EXCLUDE_FROM_BACKUP,
    LOGGER,
)
from .models import BackupUploadMetadata, BaseBackup
from .util import read_backup

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
        self.local_backup_agents: dict[str, LocalBackupAgent] = {}
        self.config = BackupConfig(hass)
        self.syncing = False

    async def async_setup(self) -> None:
        """Set up the backup manager."""
        await self.config.load()
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
        self.local_backup_agents.update(
            {
                f"{integration_domain}.{agent.name}": agent
                for agent in agents
                if isinstance(agent, LocalBackupAgent)
            }
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
        agent_id: str,
        password: str | None,
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
    async def async_get_backups(
        self, **kwargs: Any
    ) -> tuple[dict[str, Backup], dict[str, Exception]]:
        """Get backups.

        Return a dictionary of Backup instances keyed by their slug.
        """

    @abc.abstractmethod
    async def async_get_backup(
        self, *, slug: str, **kwargs: Any
    ) -> tuple[_BackupT | None, dict[str, Exception]]:
        """Get a backup."""

    @abc.abstractmethod
    async def async_remove_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Remove a backup."""

    @abc.abstractmethod
    async def async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        contents: aiohttp.BodyPartReader,
        **kwargs: Any,
    ) -> None:
        """Receive and store a backup file from upload."""


class BackupManager(BaseBackupManager[Backup]):
    """Backup manager for the Backup integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup manager."""
        super().__init__(hass=hass)
        self.temp_backup_dir = Path(hass.config.path("tmp_backups"))

    async def _async_upload_backup(
        self,
        *,
        backup: BaseBackup,
        agent_ids: list[str],
        path: Path,
    ) -> None:
        """Upload a backup to selected agents."""
        self.syncing = True
        try:
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
                    LOGGER.exception(
                        "Error during backup upload - %s", result, exc_info=result
                    )
        finally:
            self.syncing = False

    async def async_get_backups(
        self, **kwargs: Any
    ) -> tuple[dict[str, Backup], dict[str, Exception]]:
        """Return backups."""
        backups: dict[str, Backup] = {}
        agent_errors: dict[str, Exception] = {}
        agent_ids = list(self.backup_agents)

        list_backups_results = await asyncio.gather(
            *(agent.async_list_backups() for agent in self.backup_agents.values()),
            return_exceptions=True,
        )
        for idx, result in enumerate(list_backups_results):
            if isinstance(result, BackupAgentError):
                agent_errors[agent_ids[idx]] = result
                continue
            if isinstance(result, BaseException):
                raise result
            for agent_backup in result:
                if agent_backup.slug not in backups:
                    backups[agent_backup.slug] = Backup(
                        slug=agent_backup.slug,
                        name=agent_backup.name,
                        date=agent_backup.date,
                        agent_ids=[],
                        size=agent_backup.size,
                        protected=agent_backup.protected,
                    )
                backups[agent_backup.slug].agent_ids.append(agent_ids[idx])

        return (backups, agent_errors)

    async def async_get_backup(
        self, *, slug: str, **kwargs: Any
    ) -> tuple[Backup | None, dict[str, Exception]]:
        """Return a backup."""
        backup: Backup | None = None
        agent_errors: dict[str, Exception] = {}
        agent_ids = list(self.backup_agents.keys())

        get_backup_results = await asyncio.gather(
            *(
                agent.async_get_backup(slug=slug)
                for agent in self.backup_agents.values()
            ),
            return_exceptions=True,
        )
        for idx, result in enumerate(get_backup_results):
            if isinstance(result, BackupAgentError):
                agent_errors[agent_ids[idx]] = result
                continue
            if isinstance(result, BaseException):
                raise result
            if not result:
                continue
            if backup is None:
                backup = Backup(
                    slug=result.slug,
                    name=result.name,
                    date=result.date,
                    agent_ids=[],
                    size=result.size,
                    protected=result.protected,
                )
                backup.agent_ids.append(agent_ids[idx])

        return (backup, agent_errors)

    async def async_remove_backup(self, *, slug: str, **kwargs: Any) -> None:
        """Remove a backup."""
        for agent in self.backup_agents.values():
            if not hasattr(agent, "async_remove_backup"):
                continue
            await agent.async_remove_backup(slug=slug)

    async def async_receive_backup(
        self,
        *,
        agent_ids: list[str],
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

        def _copy_and_cleanup(local_file_paths: list[Path], backup: BaseBackup) -> Path:
            if local_file_paths:
                tar_file_path = local_file_paths[0]
            else:
                tar_file_path = self.temp_backup_dir / f"{backup.slug}.tar"
            for local_path in local_file_paths:
                shutil.copy(target_temp_file, local_path)
            temp_dir_handler.cleanup()
            return tar_file_path

        try:
            backup = await self.hass.async_add_executor_job(
                read_backup, target_temp_file
            )
        except (OSError, tarfile.TarError, json.JSONDecodeError, KeyError) as err:
            LOGGER.warning("Unable to parse backup %s: %s", target_temp_file, err)
            return

        local_file_paths = [
            self.local_backup_agents[agent_id].get_backup_path(backup.slug)
            for agent_id in agent_ids
            if agent_id in self.local_backup_agents
        ]
        tar_file_path = await self.hass.async_add_executor_job(
            _copy_and_cleanup, local_file_paths, backup
        )
        await self._async_upload_backup(
            backup=backup, agent_ids=agent_ids, path=tar_file_path
        )
        if not local_file_paths:
            await self.hass.async_add_executor_job(tar_file_path.unlink, True)

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
    ) -> BaseBackup:
        """Generate a backup."""
        success = False

        local_file_paths = [
            self.local_backup_agents[agent_id].get_backup_path(slug)
            for agent_id in agent_ids
            if agent_id in self.local_backup_agents
        ]

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

            tar_file_path, size_in_bytes = await self.hass.async_add_executor_job(
                self._mkdir_and_generate_backup_contents,
                local_file_paths,
                backup_data,
                database_included,
                password,
            )
            backup = BaseBackup(
                slug=slug,
                name=backup_name,
                date=date_str,
                size=round(size_in_bytes / 1_048_576, 2),
                protected=password is not None,
            )
            LOGGER.debug(
                "Generated new backup with slug %s, uploading to agents %s",
                slug,
                agent_ids,
            )
            await self._async_upload_backup(
                backup=backup, agent_ids=agent_ids, path=tar_file_path
            )
            if not local_file_paths:
                await self.hass.async_add_executor_job(tar_file_path.unlink, True)
            success = True
            return backup
        finally:
            if on_progress:
                on_progress(BackupProgress(done=True, stage=None, success=success))
            self.backup_task = None
            await self.async_post_backup_actions()

    def _mkdir_and_generate_backup_contents(
        self,
        tar_file_paths: list[Path],
        backup_data: dict[str, Any],
        database_included: bool,
        password: str | None,
    ) -> tuple[Path, int]:
        """Generate backup contents and return the size."""
        if tar_file_paths:
            tar_file_path = tar_file_paths[0]
        else:
            tar_file_path = self.temp_backup_dir / f"{backup_data['slug']}.tar"
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
        for local_path in tar_file_paths[1:]:
            shutil.copy(tar_file_path, local_path)
        return (tar_file_path, tar_file_path.stat().st_size)

    async def async_restore_backup(
        self,
        slug: str,
        *,
        agent_id: str,
        password: str | None,
        **kwargs: Any,
    ) -> None:
        """Restore a backup.

        This will write the restore information to .HA_RESTORE which
        will be handled during startup by the restore_backup module.
        """

        if agent_id in self.local_backup_agents:
            local_agent = self.local_backup_agents[agent_id]
            if not await local_agent.async_get_backup(slug=slug):
                raise HomeAssistantError(f"Backup {slug} not found in agent {agent_id}")
            path = local_agent.get_backup_path(slug=slug)
        else:
            path = self.temp_backup_dir / f"{slug}.tar"
            agent = self.backup_agents[agent_id]
            if not (backup := await agent.async_get_backup(slug=slug)):
                raise HomeAssistantError(f"Backup {slug} not found in agent {agent_id}")
            await agent.async_download_backup(id=backup.id, path=path)

        path = local_agent.get_backup_path(slug)

        def _write_restore_file() -> None:
            """Write the restore file."""
            Path(self.hass.config.path(RESTORE_BACKUP_FILE)).write_text(
                json.dumps({"path": path.as_posix(), "password": password}),
                encoding="utf-8",
            )

        await self.hass.async_add_executor_job(_write_restore_file)
        await self.hass.services.async_call("homeassistant", "restart", {})


def _generate_slug(date: str, name: str) -> str:
    """Generate a backup slug."""
    return hashlib.sha1(f"{date} - {name}".lower().encode()).hexdigest()[:8]
