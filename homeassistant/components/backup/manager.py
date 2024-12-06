"""Backup manager for the Backup integration."""

from __future__ import annotations

import abc
import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import time
from typing import TYPE_CHECKING, Any, Protocol

import aiohttp
from securetar import SecureTarFile, atomic_contents_add

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
    DATA_MANAGER,
    DOMAIN,
    EXCLUDE_DATABASE_FROM_BACKUP,
    EXCLUDE_FROM_BACKUP,
    LOGGER,
)
from .models import AgentBackup, Folder
from .util import make_backup_dir, read_backup


@dataclass(frozen=True, kw_only=True, slots=True)
class NewBackup:
    """New backup class."""

    backup_job_id: str


@dataclass(frozen=True, kw_only=True, slots=True)
class Backup(AgentBackup):
    """Backup class."""

    agent_ids: list[str]


@dataclass(frozen=True, kw_only=True, slots=True)
class WrittenBackup:
    """Written backup class."""

    backup: AgentBackup
    open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]]
    release_stream: Callable[[], Coroutine[Any, Any, None]]


class BackupManagerState(StrEnum):
    """Backup state type."""

    IDLE = "idle"
    CREATE_BACKUP = "create_backup"
    RECEIVE_BACKUP = "receive_backup"
    RESTORE_BACKUP = "restore_backup"


class CreateBackupStage(StrEnum):
    """Create backup stage enum."""

    ADDON_REPOSITORIES = "addon_repositories"
    ADDONS = "addons"
    AWAIT_ADDON_RESTARTS = "await_addon_restarts"
    DOCKER_CONFIG = "docker_config"
    FINISHING_FILE = "finishing_file"
    FOLDERS = "folders"
    HOME_ASSISTANT = "home_assistant"
    UPLOAD_TO_AGENTS = "upload_to_agents"


class CreateBackupState(StrEnum):
    """Create backup state enum."""

    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


class ReceiveBackupStage(StrEnum):
    """Receive backup stage enum."""

    RECEIVE_FILE = "receive_file"
    UPLOAD_TO_AGENTS = "upload_to_agents"


class ReceiveBackupState(StrEnum):
    """Receive backup state enum."""

    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


class RestoreBackupStage(StrEnum):
    """Restore backup stage enum."""

    ADDON_REPOSITORIES = "addon_repositories"
    ADDONS = "addons"
    AWAIT_ADDON_RESTARTS = "await_addon_restarts"
    AWAIT_HOME_ASSISTANT_RESTART = "await_home_assistant_restart"
    CHECK_HOME_ASSISTANT = "check_home_assistant"
    DOCKER_CONFIG = "docker_config"
    DOWNLOAD_FROM_AGENT = "download_from_agent"
    FOLDERS = "folders"
    HOME_ASSISTANT = "home_assistant"
    REMOVE_DELTA_ADDONS = "remove_delta_addons"


class RestoreBackupState(StrEnum):
    """Receive backup state enum."""

    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


@dataclass(frozen=True, kw_only=True, slots=True)
class ManagerStateEvent:
    """Backup state class."""

    manager_state: BackupManagerState


@dataclass(frozen=True, kw_only=True, slots=True)
class IdleEvent(ManagerStateEvent):
    """Backup manager idle."""

    manager_state: BackupManagerState = BackupManagerState.IDLE


@dataclass(frozen=True, kw_only=True, slots=True)
class CreateBackupEvent(ManagerStateEvent):
    """Backup in progress."""

    manager_state: BackupManagerState = BackupManagerState.CREATE_BACKUP
    stage: CreateBackupStage | None
    state: CreateBackupState


@dataclass(frozen=True, kw_only=True, slots=True)
class ReceiveBackupEvent(ManagerStateEvent):
    """Backup receive."""

    manager_state: BackupManagerState = BackupManagerState.RECEIVE_BACKUP
    stage: ReceiveBackupStage | None
    state: ReceiveBackupState


@dataclass(frozen=True, kw_only=True, slots=True)
class RestoreBackupEvent(ManagerStateEvent):
    """Backup restore."""

    manager_state: BackupManagerState = BackupManagerState.RESTORE_BACKUP
    stage: RestoreBackupStage | None
    state: RestoreBackupState


class BackupPlatformProtocol(Protocol):
    """Define the format that backup platforms can have."""

    async def async_pre_backup(self, hass: HomeAssistant) -> None:
        """Perform operations before a backup starts."""

    async def async_post_backup(self, hass: HomeAssistant) -> None:
        """Perform operations after a backup finishes."""


class BackupReaderWriter(abc.ABC):
    """Abstract class for reading and writing backups."""

    temp_backup_dir: Path

    @abc.abstractmethod
    async def async_create_backup(
        self,
        *,
        agent_ids: list[str],
        backup_name: str,
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        on_progress: Callable[[ManagerStateEvent], None],
        password: str | None,
    ) -> tuple[NewBackup, asyncio.Task[WrittenBackup]]:
        """Create a backup."""

    @abc.abstractmethod
    async def async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        stream: AsyncIterator[bytes],
        suggested_filename: str,
    ) -> WrittenBackup:
        """Receive a backup."""

    @abc.abstractmethod
    async def async_restore_backup(
        self,
        backup_id: str,
        *,
        agent_id: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        password: str | None,
        restore_addons: list[str] | None,
        restore_database: bool,
        restore_folders: list[Folder] | None,
        restore_homeassistant: bool,
    ) -> None:
        """Restore a backup."""


class BackupManager:
    """Define the format that backup managers can have."""

    def __init__(self, hass: HomeAssistant, reader_writer: BackupReaderWriter) -> None:
        """Initialize the backup manager."""
        self.hass = hass
        self.platforms: dict[str, BackupPlatformProtocol] = {}
        self.backup_agents: dict[str, BackupAgent] = {}
        self.local_backup_agents: dict[str, LocalBackupAgent] = {}

        self.config = BackupConfig(hass, self)
        self._reader_writer = reader_writer

        # Tasks and flags tracking backup and restore progress
        self.backup_task: asyncio.Task[WrittenBackup] | None = None
        self.backup_finish_task: asyncio.Task[None] | None = None

        # Backup schedule and retention listeners
        self.remove_next_backup_event: Callable[[], None] | None = None
        self.remove_next_delete_event: Callable[[], None] | None = None

        # Latest backup event and backup event subscribers
        self.last_event: ManagerStateEvent = IdleEvent()
        self._backup_event_subscriptions: list[Callable[[ManagerStateEvent], None]] = []

    async def async_setup(self) -> None:
        """Set up the backup manager."""
        await self.config.load()
        await self.load_platforms()

    @property
    def state(self) -> BackupManagerState:
        """Return the state of the backup manager."""
        return self.last_event.manager_state

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

    async def async_pre_backup_actions(self) -> None:
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

    async def async_post_backup_actions(self) -> None:
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

    async def _async_upload_backup(
        self,
        *,
        backup: AgentBackup,
        agent_ids: list[str],
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
    ) -> None:
        """Upload a backup to selected agents."""
        LOGGER.debug("Uploading backup %s to agents %s", backup.backup_id, agent_ids)

        sync_backup_results = await asyncio.gather(
            *(
                self.backup_agents[agent_id].async_upload_backup(
                    open_stream=open_stream,
                    backup=backup,
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

    async def async_get_backups(self) -> tuple[dict[str, Backup], dict[str, Exception]]:
        """Get backups.

        Return a dictionary of Backup instances keyed by their ID.
        """
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
                if agent_backup.backup_id not in backups:
                    backups[agent_backup.backup_id] = Backup(
                        agent_ids=[],
                        addons=agent_backup.addons,
                        backup_id=agent_backup.backup_id,
                        date=agent_backup.date,
                        database_included=agent_backup.database_included,
                        folders=agent_backup.folders,
                        homeassistant_included=agent_backup.homeassistant_included,
                        homeassistant_version=agent_backup.homeassistant_version,
                        name=agent_backup.name,
                        protected=agent_backup.protected,
                        size=agent_backup.size,
                    )
                backups[agent_backup.backup_id].agent_ids.append(agent_ids[idx])

        return (backups, agent_errors)

    async def async_get_backup(
        self, backup_id: str
    ) -> tuple[Backup | None, dict[str, Exception]]:
        """Get a backup."""
        backup: Backup | None = None
        agent_errors: dict[str, Exception] = {}
        agent_ids = list(self.backup_agents)

        get_backup_results = await asyncio.gather(
            *(
                agent.async_get_backup(backup_id)
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
                    agent_ids=[],
                    addons=result.addons,
                    backup_id=result.backup_id,
                    date=result.date,
                    database_included=result.database_included,
                    folders=result.folders,
                    homeassistant_included=result.homeassistant_included,
                    homeassistant_version=result.homeassistant_version,
                    name=result.name,
                    protected=result.protected,
                    size=result.size,
                )
            backup.agent_ids.append(agent_ids[idx])

        return (backup, agent_errors)

    async def async_delete_backup(self, backup_id: str) -> dict[str, Exception]:
        """Delete a backup."""
        agent_errors: dict[str, Exception] = {}
        agent_ids = list(self.backup_agents)

        delete_backup_results = await asyncio.gather(
            *(
                agent.async_delete_backup(backup_id)
                for agent in self.backup_agents.values()
            ),
            return_exceptions=True,
        )
        for idx, result in enumerate(delete_backup_results):
            if isinstance(result, BackupAgentError):
                agent_errors[agent_ids[idx]] = result
                continue
            if isinstance(result, BaseException):
                raise result

        return agent_errors

    async def async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        contents: aiohttp.BodyPartReader,
    ) -> None:
        """Receive and store a backup file from upload."""
        if self.state is not BackupManagerState.IDLE:
            raise HomeAssistantError("Backup manager busy")
        self.async_on_backup_event(
            ReceiveBackupEvent(stage=None, state=ReceiveBackupState.IN_PROGRESS)
        )
        try:
            await self._async_receive_backup(agent_ids=agent_ids, contents=contents)
        except Exception:
            self.async_on_backup_event(
                ReceiveBackupEvent(stage=None, state=ReceiveBackupState.FAILED)
            )
            raise
        else:
            self.async_on_backup_event(
                ReceiveBackupEvent(stage=None, state=ReceiveBackupState.COMPLETED)
            )
        finally:
            self.async_on_backup_event(IdleEvent())

    async def _async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        contents: aiohttp.BodyPartReader,
    ) -> None:
        """Receive and store a backup file from upload."""
        contents.chunk_size = BUF_SIZE
        self.async_on_backup_event(
            ReceiveBackupEvent(
                stage=ReceiveBackupStage.RECEIVE_FILE,
                state=ReceiveBackupState.IN_PROGRESS,
            )
        )
        written_backup = await self._reader_writer.async_receive_backup(
            agent_ids=agent_ids,
            stream=contents,
            suggested_filename=contents.filename or "backup.tar",
        )
        self.async_on_backup_event(
            ReceiveBackupEvent(
                stage=ReceiveBackupStage.UPLOAD_TO_AGENTS,
                state=ReceiveBackupState.IN_PROGRESS,
            )
        )
        await self._async_upload_backup(
            backup=written_backup.backup,
            agent_ids=agent_ids,
            open_stream=written_backup.open_stream,
        )
        await written_backup.release_stream()

    async def async_create_backup(
        self,
        *,
        agent_ids: list[str],
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        name: str | None,
        password: str | None,
    ) -> NewBackup:
        """Initiate generating a backup."""
        if self.state is not BackupManagerState.IDLE:
            raise HomeAssistantError("Backup manager busy")

        self.async_on_backup_event(
            CreateBackupEvent(stage=None, state=CreateBackupState.IN_PROGRESS)
        )
        try:
            return await self._async_create_backup(
                agent_ids=agent_ids,
                include_addons=include_addons,
                include_all_addons=include_all_addons,
                include_database=include_database,
                include_folders=include_folders,
                include_homeassistant=include_homeassistant,
                name=name,
                password=password,
            )
        except Exception:
            self.async_on_backup_event(
                CreateBackupEvent(stage=None, state=CreateBackupState.FAILED)
            )
            self.async_on_backup_event(IdleEvent())
            raise

    async def _async_create_backup(
        self,
        *,
        agent_ids: list[str],
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        name: str | None,
        password: str | None,
    ) -> NewBackup:
        """Initiate generating a backup."""
        if not agent_ids:
            raise HomeAssistantError("At least one agent must be selected")
        if any(agent_id not in self.backup_agents for agent_id in agent_ids):
            raise HomeAssistantError("Invalid agent selected")
        if include_all_addons and include_addons:
            raise HomeAssistantError(
                "Cannot include all addons and specify specific addons"
            )

        backup_name = name or f"Core {HAVERSION}"
        new_backup, self.backup_task = await self._reader_writer.async_create_backup(
            agent_ids=agent_ids,
            backup_name=backup_name,
            include_addons=include_addons,
            include_all_addons=include_all_addons,
            include_database=include_database,
            include_folders=include_folders,
            include_homeassistant=include_homeassistant,
            on_progress=self.async_on_backup_event,
            password=password,
        )
        self.backup_finish_task = self.hass.async_create_task(
            self._async_finish_backup(agent_ids),
            name="backup_manager_finish_backup",
        )
        return new_backup

    async def _async_finish_backup(self, agent_ids: list[str]) -> None:
        if TYPE_CHECKING:
            assert self.backup_task is not None
        try:
            written_backup = await self.backup_task
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Generating backup failed", exc_info=err)
            self.async_on_backup_event(
                CreateBackupEvent(stage=None, state=CreateBackupState.FAILED)
            )
        else:
            LOGGER.debug(
                "Generated new backup with backup_id %s, uploading to agents %s",
                written_backup.backup.backup_id,
                agent_ids,
            )
            self.async_on_backup_event(
                CreateBackupEvent(
                    stage=CreateBackupStage.UPLOAD_TO_AGENTS,
                    state=CreateBackupState.IN_PROGRESS,
                )
            )
            await self._async_upload_backup(
                backup=written_backup.backup,
                agent_ids=agent_ids,
                open_stream=written_backup.open_stream,
            )
            await written_backup.release_stream()
            self.async_on_backup_event(
                CreateBackupEvent(stage=None, state=CreateBackupState.COMPLETED)
            )
        finally:
            self.backup_task = None
            self.backup_finish_task = None
            self.last_event = IdleEvent()

    async def async_restore_backup(
        self,
        backup_id: str,
        *,
        agent_id: str,
        password: str | None,
        restore_addons: list[str] | None,
        restore_database: bool,
        restore_folders: list[Folder] | None,
        restore_homeassistant: bool,
    ) -> None:
        """Initiate restoring a backup."""
        if self.state is not BackupManagerState.IDLE:
            raise HomeAssistantError("Backup manager busy")

        self.async_on_backup_event(
            RestoreBackupEvent(stage=None, state=RestoreBackupState.IN_PROGRESS)
        )
        try:
            await self._async_restore_backup(
                backup_id=backup_id,
                agent_id=agent_id,
                password=password,
                restore_addons=restore_addons,
                restore_database=restore_database,
                restore_folders=restore_folders,
                restore_homeassistant=restore_homeassistant,
            )
        except Exception:
            self.async_on_backup_event(
                RestoreBackupEvent(stage=None, state=RestoreBackupState.FAILED)
            )
            self.async_on_backup_event(IdleEvent())
            raise

    async def _async_restore_backup(
        self,
        backup_id: str,
        *,
        agent_id: str,
        password: str | None,
        restore_addons: list[str] | None,
        restore_database: bool,
        restore_folders: list[Folder] | None,
        restore_homeassistant: bool,
    ) -> None:
        """Initiate restoring a backup."""
        agent = self.backup_agents[agent_id]
        if not await agent.async_get_backup(backup_id):
            raise HomeAssistantError(
                f"Backup {backup_id} not found in agent {agent_id}"
            )

        async def open_backup() -> AsyncIterator[bytes]:
            return await agent.async_download_backup(backup_id)

        await self._reader_writer.async_restore_backup(
            backup_id=backup_id,
            open_stream=open_backup,
            agent_id=agent_id,
            password=password,
            restore_addons=restore_addons,
            restore_database=restore_database,
            restore_folders=restore_folders,
            restore_homeassistant=restore_homeassistant,
        )

    @callback
    def async_on_backup_event(
        self,
        event: ManagerStateEvent,
    ) -> None:
        """Forward event to subscribers."""
        self.last_event = event
        for subscription in self._backup_event_subscriptions:
            subscription(event)

    @callback
    def async_subscribe_events(
        self,
        on_event: Callable[[ManagerStateEvent], None],
    ) -> Callable[[], None]:
        """Subscribe events."""

        def remove_subscription() -> None:
            self._backup_event_subscriptions.remove(on_event)

        self._backup_event_subscriptions.append(on_event)
        return remove_subscription


class CoreBackupReaderWriter(BackupReaderWriter):
    """Class for reading and writing backups in core and container installations."""

    _local_agent_id = f"{DOMAIN}.local"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup reader/writer."""
        self._hass = hass
        self.temp_backup_dir = Path(hass.config.path("tmp_backups"))

    async def async_create_backup(
        self,
        *,
        agent_ids: list[str],
        backup_name: str,
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        on_progress: Callable[[ManagerStateEvent], None],
        password: str | None,
    ) -> tuple[NewBackup, asyncio.Task[WrittenBackup]]:
        """Initiate generating a backup."""
        date_str = dt_util.now().isoformat()
        backup_id = _generate_backup_id(date_str, backup_name)

        if include_addons or include_all_addons or include_folders:
            raise HomeAssistantError(
                "Addons and folders are not supported by core backup"
            )
        if not include_homeassistant:
            raise HomeAssistantError("Home Assistant must be included in backup")

        backup_task = self._hass.async_create_task(
            self._async_create_backup(
                agent_ids=agent_ids,
                backup_id=backup_id,
                backup_name=backup_name,
                include_database=include_database,
                date_str=date_str,
                on_progress=on_progress,
                password=password,
            ),
            name="backup_manager_create_backup",
            eager_start=False,  # To ensure the task is not started before we return
        )

        return (NewBackup(backup_job_id=backup_id), backup_task)

    async def _async_create_backup(
        self,
        *,
        agent_ids: list[str],
        backup_id: str,
        backup_name: str,
        date_str: str,
        include_database: bool,
        on_progress: Callable[[ManagerStateEvent], None],
        password: str | None,
    ) -> WrittenBackup:
        """Generate a backup."""
        manager = self._hass.data[DATA_MANAGER]

        suggested_tar_file_path = None
        if self._local_agent_id in agent_ids:
            local_agent = manager.local_backup_agents[self._local_agent_id]
            suggested_tar_file_path = local_agent.get_backup_path(backup_id)

        on_progress(
            CreateBackupEvent(
                stage=CreateBackupStage.HOME_ASSISTANT,
                state=CreateBackupState.IN_PROGRESS,
            )
        )
        try:
            # Inform integrations a backup is about to be made
            await manager.async_pre_backup_actions()

            backup_data = {
                "compressed": True,
                "date": date_str,
                "homeassistant": {
                    "exclude_database": not include_database,
                    "version": HAVERSION,
                },
                "name": backup_name,
                "protected": password is not None,
                "slug": backup_id,
                "type": "partial",
                "version": 2,
            }

            tar_file_path, size_in_bytes = await self._hass.async_add_executor_job(
                self._mkdir_and_generate_backup_contents,
                backup_data,
                include_database,
                password,
                suggested_tar_file_path,
            )
            backup = AgentBackup(
                addons=[],
                backup_id=backup_id,
                database_included=include_database,
                date=date_str,
                folders=[],
                homeassistant_included=True,
                homeassistant_version=HAVERSION,
                name=backup_name,
                protected=password is not None,
                size=size_in_bytes,
            )

            async_add_executor_job = self._hass.async_add_executor_job

            async def send_backup() -> AsyncIterator[bytes]:
                f = await async_add_executor_job(tar_file_path.open, "rb")
                try:
                    while chunk := await async_add_executor_job(f.read, 2**20):
                        yield chunk
                finally:
                    await async_add_executor_job(f.close)

            async def open_backup() -> AsyncIterator[bytes]:
                return send_backup()

            async def remove_backup() -> None:
                if not suggested_tar_file_path:
                    return
                await async_add_executor_job(suggested_tar_file_path.unlink, True)

            return WrittenBackup(
                backup=backup, open_stream=open_backup, release_stream=remove_backup
            )
        finally:
            # Inform integrations the backup is done
            await manager.async_post_backup_actions()

    def _mkdir_and_generate_backup_contents(
        self,
        backup_data: dict[str, Any],
        database_included: bool,
        password: str | None,
        tar_file_path: Path | None,
    ) -> tuple[Path, int]:
        """Generate backup contents and return the size."""
        if not tar_file_path:
            tar_file_path = self.temp_backup_dir / f"{backup_data['slug']}.tar"
        make_backup_dir(tar_file_path.parent)

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
                    origin_path=Path(self._hass.config.path()),
                    excludes=excludes,
                    arcname="data",
                )
        return (tar_file_path, tar_file_path.stat().st_size)

    async def async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        stream: AsyncIterator[bytes],
        suggested_filename: str,
    ) -> WrittenBackup:
        """Receive a backup."""
        temp_file = Path(self.temp_backup_dir, suggested_filename)

        async_add_executor_job = self._hass.async_add_executor_job
        await async_add_executor_job(make_backup_dir, self.temp_backup_dir)
        f = await async_add_executor_job(temp_file.open, "wb")
        try:
            async for chunk in stream:
                await async_add_executor_job(f.write, chunk)
        finally:
            await async_add_executor_job(f.close)

        try:
            backup = await async_add_executor_job(read_backup, temp_file)
        except (OSError, tarfile.TarError, json.JSONDecodeError, KeyError) as err:
            LOGGER.warning("Unable to parse backup %s: %s", temp_file, err)
            raise

        manager = self._hass.data[DATA_MANAGER]
        if self._local_agent_id in agent_ids:
            local_agent = manager.local_backup_agents[self._local_agent_id]
            tar_file_path = local_agent.get_backup_path(backup.backup_id)
            await async_add_executor_job(shutil.move, temp_file, tar_file_path)
        else:
            tar_file_path = temp_file

        async def send_backup() -> AsyncIterator[bytes]:
            f = await async_add_executor_job(tar_file_path.open, "rb")
            try:
                while chunk := await async_add_executor_job(f.read, 2**20):
                    yield chunk
            finally:
                await async_add_executor_job(f.close)

        async def open_backup() -> AsyncIterator[bytes]:
            return send_backup()

        async def remove_backup() -> None:
            if self._local_agent_id in agent_ids:
                return
            await async_add_executor_job(temp_file.unlink, True)

        return WrittenBackup(
            backup=backup, open_stream=open_backup, release_stream=remove_backup
        )

    async def async_restore_backup(
        self,
        backup_id: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        *,
        agent_id: str,
        password: str | None,
        restore_addons: list[str] | None,
        restore_database: bool,
        restore_folders: list[Folder] | None,
        restore_homeassistant: bool,
    ) -> None:
        """Restore a backup.

        This will write the restore information to .HA_RESTORE which
        will be handled during startup by the restore_backup module.
        """

        if restore_addons or restore_folders:
            raise HomeAssistantError(
                "Addons and folders are not supported in core restore"
            )
        if not restore_homeassistant and not restore_database:
            raise HomeAssistantError(
                "Home Assistant or database must be included in restore"
            )

        manager = self._hass.data[DATA_MANAGER]
        if agent_id in manager.local_backup_agents:
            local_agent = manager.local_backup_agents[agent_id]
            path = local_agent.get_backup_path(backup_id)
            remove_after_restore = False
        else:
            async_add_executor_job = self._hass.async_add_executor_job
            path = self.temp_backup_dir / f"{backup_id}.tar"
            stream = await open_stream()
            await async_add_executor_job(make_backup_dir, self.temp_backup_dir)
            f = await async_add_executor_job(path.open, "wb")
            try:
                async for chunk in stream:
                    await async_add_executor_job(f.write, chunk)
            finally:
                await async_add_executor_job(f.close)

            remove_after_restore = True

        def _write_restore_file() -> None:
            """Write the restore file."""
            Path(self._hass.config.path(RESTORE_BACKUP_FILE)).write_text(
                json.dumps(
                    {
                        "path": path.as_posix(),
                        "password": password,
                        "remove_after_restore": remove_after_restore,
                        "restore_database": restore_database,
                        "restore_homeassistant": restore_homeassistant,
                    }
                ),
                encoding="utf-8",
            )

        await self._hass.async_add_executor_job(_write_restore_file)
        await self._hass.services.async_call("homeassistant", "restart", {})


def _generate_backup_id(date: str, name: str) -> str:
    """Generate a backup ID."""
    return hashlib.sha1(f"{date} - {name}".lower().encode()).hexdigest()[:8]
