"""Backup manager for the Backup integration."""

from __future__ import annotations

import abc
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
import io
from itertools import chain
import json
from pathlib import Path, PurePath
import shutil
import sys
import tarfile
import time
from typing import IO, TYPE_CHECKING, Any, Protocol, TypedDict, cast

import aiohttp
from securetar import SecureTarFile, atomic_contents_add

from homeassistant.backup_restore import (
    RESTORE_BACKUP_FILE,
    RESTORE_BACKUP_RESULT_FILE,
    password_to_key,
)
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    frame,
    instance_id,
    integration_platform,
    issue_registry as ir,
    start,
)
from homeassistant.helpers.backup import DATA_BACKUP
from homeassistant.helpers.json import json_bytes
from homeassistant.util import dt as dt_util, json as json_util

from . import util as backup_util
from .agent import (
    BackupAgent,
    BackupAgentError,
    BackupAgentPlatformProtocol,
    LocalBackupAgent,
)
from .config import (
    BackupConfig,
    CreateBackupParametersDict,
    check_unavailable_agents,
    delete_backups_exceeding_configured_count,
)
from .const import (
    BUF_SIZE,
    DATA_MANAGER,
    DOMAIN,
    EXCLUDE_DATABASE_FROM_BACKUP,
    EXCLUDE_FROM_BACKUP,
    LOGGER,
)
from .models import (
    AgentBackup,
    BackupError,
    BackupManagerError,
    BackupNotFound,
    BackupReaderWriterError,
    BaseBackup,
    Folder,
)
from .store import BackupStore
from .util import (
    AsyncIteratorReader,
    DecryptedBackupStreamer,
    EncryptedBackupStreamer,
    make_backup_dir,
    read_backup,
    validate_password,
    validate_password_stream,
)


@dataclass(frozen=True, kw_only=True, slots=True)
class NewBackup:
    """New backup class."""

    backup_job_id: str


@dataclass(frozen=True, kw_only=True, slots=True)
class AgentBackupStatus:
    """Agent specific backup attributes."""

    protected: bool
    size: int


@dataclass(frozen=True, kw_only=True, slots=True)
class ManagerBackup(BaseBackup):
    """Backup class."""

    agents: dict[str, AgentBackupStatus]
    failed_agent_ids: list[str]
    with_automatic_settings: bool | None


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
    BLOCKED = "blocked"
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
    CORE_RESTART = "core_restart"
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
    reason: str | None
    stage: CreateBackupStage | None
    state: CreateBackupState


@dataclass(frozen=True, kw_only=True, slots=True)
class ReceiveBackupEvent(ManagerStateEvent):
    """Backup receive."""

    manager_state: BackupManagerState = BackupManagerState.RECEIVE_BACKUP
    reason: str | None
    stage: ReceiveBackupStage | None
    state: ReceiveBackupState


@dataclass(frozen=True, kw_only=True, slots=True)
class RestoreBackupEvent(ManagerStateEvent):
    """Backup restore."""

    manager_state: BackupManagerState = BackupManagerState.RESTORE_BACKUP
    reason: str | None
    stage: RestoreBackupStage | None
    state: RestoreBackupState


@dataclass(frozen=True, kw_only=True, slots=True)
class BackupPlatformEvent:
    """Backup platform class."""

    domain: str


@dataclass(frozen=True, kw_only=True, slots=True)
class BlockedEvent(ManagerStateEvent):
    """Backup manager blocked, Home Assistant is starting."""

    manager_state: BackupManagerState = BackupManagerState.BLOCKED


class BackupPlatformProtocol(Protocol):
    """Define the format that backup platforms can have."""

    async def async_pre_backup(self, hass: HomeAssistant) -> None:
        """Perform operations before a backup starts."""

    async def async_post_backup(self, hass: HomeAssistant) -> None:
        """Perform operations after a backup finishes."""


class BackupReaderWriter(abc.ABC):
    """Abstract class for reading and writing backups."""

    @abc.abstractmethod
    async def async_create_backup(
        self,
        *,
        agent_ids: list[str],
        backup_name: str,
        extra_metadata: dict[str, bool | str],
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        on_progress: Callable[[CreateBackupEvent], None],
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
        on_progress: Callable[[RestoreBackupEvent], None],
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        password: str | None,
        restore_addons: list[str] | None,
        restore_database: bool,
        restore_folders: list[Folder] | None,
        restore_homeassistant: bool,
    ) -> None:
        """Restore a backup."""

    @abc.abstractmethod
    async def async_resume_restore_progress_after_restart(
        self,
        *,
        on_progress: Callable[[RestoreBackupEvent | IdleEvent], None],
    ) -> None:
        """Get restore events after core restart."""

    @abc.abstractmethod
    async def async_validate_config(self, *, config: BackupConfig) -> None:
        """Validate backup config."""


class IncorrectPasswordError(BackupReaderWriterError):
    """Raised when the password is incorrect."""

    error_code = "password_incorrect"
    _message = "The password provided is incorrect."


class DecryptOnDowloadNotSupported(BackupManagerError):
    """Raised when on-the-fly decryption is not supported."""

    error_code = "decrypt_on_download_not_supported"
    _message = "On-the-fly decryption is not supported for this backup."


class BackupManagerExceptionGroup(BackupManagerError, ExceptionGroup):
    """Raised when multiple exceptions occur."""

    error_code = "multiple_errors"


class BackupManager:
    """Define the format that backup managers can have."""

    def __init__(self, hass: HomeAssistant, reader_writer: BackupReaderWriter) -> None:
        """Initialize the backup manager."""
        self.hass = hass
        self.platforms: dict[str, BackupPlatformProtocol] = {}
        self.backup_agent_platforms: dict[str, BackupAgentPlatformProtocol] = {}
        self.backup_agents: dict[str, BackupAgent] = {}
        self.local_backup_agents: dict[str, LocalBackupAgent] = {}

        self.config = BackupConfig(hass, self)
        self._reader_writer = reader_writer
        self.known_backups = KnownBackups(self)
        self.store = BackupStore(hass, self)

        # Tasks and flags tracking backup and restore progress
        self._backup_task: asyncio.Task[WrittenBackup] | None = None
        self._backup_finish_task: asyncio.Task[None] | None = None

        # Backup schedule and retention listeners
        self.remove_next_backup_event: Callable[[], None] | None = None
        self.remove_next_delete_event: Callable[[], None] | None = None

        # Latest backup event and backup event subscribers
        self.last_event: ManagerStateEvent = BlockedEvent()
        self.last_action_event: ManagerStateEvent | None = None
        self._backup_event_subscriptions = hass.data[
            DATA_BACKUP
        ].backup_event_subscriptions
        self._backup_platform_event_subscriptions = hass.data[
            DATA_BACKUP
        ].backup_platform_event_subscriptions

    async def async_setup(self) -> None:
        """Set up the backup manager."""
        stored = await self.store.load()
        if stored:
            self.config.load(stored["config"])
            self.known_backups.load(stored["backups"])

        await self._reader_writer.async_validate_config(config=self.config)

        await self._reader_writer.async_resume_restore_progress_after_restart(
            on_progress=self.async_on_backup_event
        )

        async def set_manager_idle_after_start(hass: HomeAssistant) -> None:
            """Set manager to idle after start."""
            self.async_on_backup_event(IdleEvent())

        if self.state == BackupManagerState.BLOCKED:
            # If we're not finishing a restore job, set the manager to idle after start
            start.async_at_started(self.hass, set_manager_idle_after_start)

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

    @callback
    def _async_add_backup_agent_platform(
        self,
        integration_domain: str,
        platform: BackupAgentPlatformProtocol,
    ) -> None:
        """Add backup agent platform to the backup manager."""
        if not hasattr(platform, "async_get_backup_agents"):
            return

        self.backup_agent_platforms[integration_domain] = platform

        @callback
        def listener() -> None:
            LOGGER.debug("Loading backup agents for %s", integration_domain)
            self.hass.async_create_task(
                self._async_reload_backup_agents(integration_domain)
            )

        if hasattr(platform, "async_register_backup_agents_listener"):
            platform.async_register_backup_agents_listener(self.hass, listener=listener)

        listener()

    async def _async_reload_backup_agents(self, domain: str) -> None:
        """Add backup agent platform to the backup manager."""
        platform = self.backup_agent_platforms[domain]

        # Remove all agents for the domain
        for agent_id in list(self.backup_agents):
            if self.backup_agents[agent_id].domain == domain:
                del self.backup_agents[agent_id]
        for agent_id in list(self.local_backup_agents):
            if self.local_backup_agents[agent_id].domain == domain:
                del self.local_backup_agents[agent_id]

        # Add new agents
        agents = await platform.async_get_backup_agents(self.hass)
        self.backup_agents.update({agent.agent_id: agent for agent in agents})
        self.local_backup_agents.update(
            {
                agent.agent_id: agent
                for agent in agents
                if isinstance(agent, LocalBackupAgent)
            }
        )

        @callback
        def check_unavailable_agents_after_start(hass: HomeAssistant) -> None:
            """Check unavailable agents after start."""
            check_unavailable_agents(hass, self)

        start.async_at_started(self.hass, check_unavailable_agents_after_start)

    async def _add_platform(
        self,
        hass: HomeAssistant,
        integration_domain: str,
        platform: Any,
    ) -> None:
        """Add a backup platform manager."""
        self._add_platform_pre_post_handler(integration_domain, platform)
        self._async_add_backup_agent_platform(integration_domain, platform)
        LOGGER.debug("Backup platform %s loaded", integration_domain)
        LOGGER.debug("%s platforms loaded in total", len(self.platforms))
        LOGGER.debug("%s agents loaded in total", len(self.backup_agents))
        LOGGER.debug("%s local agents loaded in total", len(self.local_backup_agents))
        event = BackupPlatformEvent(domain=integration_domain)
        for subscription in self._backup_platform_event_subscriptions:
            subscription(event)

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
                raise BackupManagerError(
                    f"Error during pre-backup: {result}"
                ) from result

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
                raise BackupManagerError(
                    f"Error during post-backup: {result}"
                ) from result

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
        password: str | None,
    ) -> dict[str, Exception]:
        """Upload a backup to selected agents."""
        agent_errors: dict[str, Exception] = {}

        LOGGER.debug("Uploading backup %s to agents %s", backup.backup_id, agent_ids)

        async def upload_backup_to_agent(agent_id: str) -> None:
            """Upload backup to a single agent, and encrypt or decrypt as needed."""
            config = self.config.data.agents.get(agent_id)
            should_encrypt = config.protected if config else password is not None
            streamer: DecryptedBackupStreamer | EncryptedBackupStreamer | None = None
            if should_encrypt == backup.protected or password is None:
                # The backup we're uploading is already in the correct state, or we
                # don't have a password to encrypt or decrypt it
                LOGGER.debug(
                    "Uploading backup %s to agent %s as is", backup.backup_id, agent_id
                )
                open_stream_func = open_stream
                _backup = backup
            elif should_encrypt:
                # The backup we're uploading is not encrypted, but the agent requires it
                LOGGER.debug(
                    "Uploading encrypted backup %s to agent %s",
                    backup.backup_id,
                    agent_id,
                )
                streamer = EncryptedBackupStreamer(
                    self.hass, backup, open_stream, password
                )
            else:
                # The backup we're uploading is encrypted, but the agent requires it
                # decrypted
                LOGGER.debug(
                    "Uploading decrypted backup %s to agent %s",
                    backup.backup_id,
                    agent_id,
                )
                streamer = DecryptedBackupStreamer(
                    self.hass, backup, open_stream, password
                )
            if streamer:
                open_stream_func = streamer.open_stream
                _backup = replace(
                    backup, protected=should_encrypt, size=streamer.size()
                )
            await self.backup_agents[agent_id].async_upload_backup(
                open_stream=open_stream_func,
                backup=_backup,
            )
            if streamer:
                await streamer.wait()

        sync_backup_results = await asyncio.gather(
            *(upload_backup_to_agent(agent_id) for agent_id in agent_ids),
            return_exceptions=True,
        )
        for idx, result in enumerate(sync_backup_results):
            agent_id = agent_ids[idx]
            if isinstance(result, BackupReaderWriterError):
                # writer errors will affect all agents
                # no point in continuing
                raise BackupManagerError(str(result)) from result
            if isinstance(result, BackupAgentError):
                agent_errors[agent_id] = result
                LOGGER.error("Upload failed for %s: %s", agent_id, result)
                continue
            if isinstance(result, Exception):
                # trap bugs from agents
                agent_errors[agent_id] = result
                LOGGER.error(
                    "Unexpected error for %s: %s", agent_id, result, exc_info=result
                )
                continue
            if isinstance(result, BaseException):
                raise result

        return agent_errors

    async def async_get_backups(
        self,
    ) -> tuple[dict[str, ManagerBackup], dict[str, Exception]]:
        """Get backups.

        Return a dictionary of Backup instances keyed by their ID.
        """
        backups: dict[str, ManagerBackup] = {}
        agent_errors: dict[str, Exception] = {}
        agent_ids = list(self.backup_agents)

        list_backups_results = await asyncio.gather(
            *(agent.async_list_backups() for agent in self.backup_agents.values()),
            return_exceptions=True,
        )
        for idx, result in enumerate(list_backups_results):
            agent_id = agent_ids[idx]
            if isinstance(result, BackupAgentError):
                agent_errors[agent_id] = result
                continue
            if isinstance(result, Exception):
                agent_errors[agent_id] = result
                LOGGER.error(
                    "Unexpected error for %s: %s", agent_id, result, exc_info=result
                )
                continue
            if isinstance(result, BaseException):
                raise result  # unexpected error
            for agent_backup in result:
                if (backup_id := agent_backup.backup_id) not in backups:
                    if known_backup := self.known_backups.get(backup_id):
                        failed_agent_ids = known_backup.failed_agent_ids
                    else:
                        failed_agent_ids = []
                    with_automatic_settings = self.is_our_automatic_backup(
                        agent_backup, await instance_id.async_get(self.hass)
                    )
                    backups[backup_id] = ManagerBackup(
                        agents={},
                        addons=agent_backup.addons,
                        backup_id=backup_id,
                        date=agent_backup.date,
                        database_included=agent_backup.database_included,
                        extra_metadata=agent_backup.extra_metadata,
                        failed_agent_ids=failed_agent_ids,
                        folders=agent_backup.folders,
                        homeassistant_included=agent_backup.homeassistant_included,
                        homeassistant_version=agent_backup.homeassistant_version,
                        name=agent_backup.name,
                        with_automatic_settings=with_automatic_settings,
                    )
                backups[backup_id].agents[agent_id] = AgentBackupStatus(
                    protected=agent_backup.protected,
                    size=agent_backup.size,
                )

        return (backups, agent_errors)

    async def async_get_backup(
        self, backup_id: str
    ) -> tuple[ManagerBackup | None, dict[str, Exception]]:
        """Get a backup."""
        backup: ManagerBackup | None = None
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
            agent_id = agent_ids[idx]
            if isinstance(result, BackupNotFound):
                continue
            if isinstance(result, BackupAgentError):
                agent_errors[agent_id] = result
                continue
            if isinstance(result, Exception):
                agent_errors[agent_id] = result
                LOGGER.error(
                    "Unexpected error for %s: %s", agent_id, result, exc_info=result
                )
                continue
            if isinstance(result, BaseException):
                raise result  # unexpected error
            # Check for None to be backwards compatible with the old BackupAgent API,
            # this can be removed in HA Core 2025.10
            if not result:
                frame.report_usage(
                    "returns None from BackupAgent.async_get_backup",
                    breaks_in_ha_version="2025.10",
                    integration_domain=agent_id.partition(".")[0],
                )
                continue
            if backup is None:
                if known_backup := self.known_backups.get(backup_id):
                    failed_agent_ids = known_backup.failed_agent_ids
                else:
                    failed_agent_ids = []
                with_automatic_settings = self.is_our_automatic_backup(
                    result, await instance_id.async_get(self.hass)
                )
                backup = ManagerBackup(
                    agents={},
                    addons=result.addons,
                    backup_id=result.backup_id,
                    date=result.date,
                    database_included=result.database_included,
                    extra_metadata=result.extra_metadata,
                    failed_agent_ids=failed_agent_ids,
                    folders=result.folders,
                    homeassistant_included=result.homeassistant_included,
                    homeassistant_version=result.homeassistant_version,
                    name=result.name,
                    with_automatic_settings=with_automatic_settings,
                )
            backup.agents[agent_id] = AgentBackupStatus(
                protected=result.protected,
                size=result.size,
            )

        return (backup, agent_errors)

    @staticmethod
    def is_our_automatic_backup(
        backup: AgentBackup, our_instance_id: str
    ) -> bool | None:
        """Check if a backup was created by us and return automatic_settings flag.

        Returns `None` if the backup was not created by us, or if the
        automatic_settings flag is not a boolean.
        """
        if backup.extra_metadata.get("instance_id") != our_instance_id:
            return None
        with_automatic_settings = backup.extra_metadata.get("with_automatic_settings")
        if not isinstance(with_automatic_settings, bool):
            return None
        return with_automatic_settings

    async def async_delete_backup(
        self, backup_id: str, *, agent_ids: list[str] | None = None
    ) -> dict[str, Exception]:
        """Delete a backup."""
        agent_errors: dict[str, Exception] = {}
        if agent_ids is None:
            agent_ids = list(self.backup_agents)

        delete_backup_results = await asyncio.gather(
            *(
                self.backup_agents[agent_id].async_delete_backup(backup_id)
                for agent_id in agent_ids
            ),
            return_exceptions=True,
        )
        for idx, result in enumerate(delete_backup_results):
            agent_id = agent_ids[idx]
            if isinstance(result, BackupNotFound):
                continue
            if isinstance(result, BackupAgentError):
                agent_errors[agent_id] = result
                continue
            if isinstance(result, Exception):
                agent_errors[agent_id] = result
                LOGGER.error(
                    "Unexpected error for %s: %s", agent_id, result, exc_info=result
                )
                continue
            if isinstance(result, BaseException):
                raise result  # unexpected error

        if not agent_errors:
            self.known_backups.remove(backup_id)

        return agent_errors

    async def async_delete_filtered_backups(
        self,
        *,
        include_filter: Callable[[dict[str, ManagerBackup]], dict[str, ManagerBackup]],
        delete_filter: Callable[[dict[str, ManagerBackup]], dict[str, ManagerBackup]],
    ) -> None:
        """Delete backups parsed with a filter.

        :param include_filter: A filter that should return the backups to consider for
        deletion. Note: The newest of the backups returned by include_filter will
        unconditionally be kept, even if delete_filter returns all backups.
        :param delete_filter: A filter that should return the backups to delete.
        """
        backups, get_agent_errors = await self.async_get_backups()
        if get_agent_errors:
            LOGGER.debug(
                "Error getting backups; continuing anyway: %s",
                get_agent_errors,
            )

        # Run the include filter first to ensure we only consider backups that
        # should be included in the deletion process.
        backups = include_filter(backups)
        backups_by_agent: dict[str, dict[str, ManagerBackup]] = defaultdict(dict)
        for backup_id, backup in backups.items():
            for agent_id in backup.agents:
                backups_by_agent[agent_id][backup_id] = backup

        LOGGER.debug("Backups returned by include filter: %s", backups)
        LOGGER.debug(
            "Backups returned by include filter by agent: %s",
            {agent_id: list(backups) for agent_id, backups in backups_by_agent.items()},
        )

        backups_to_delete = delete_filter(backups)

        LOGGER.debug("Backups returned by delete filter: %s", backups_to_delete)

        if not backups_to_delete:
            return

        # always delete oldest backup first
        backups_to_delete_by_agent: dict[str, dict[str, ManagerBackup]] = defaultdict(
            dict
        )
        for backup_id, backup in sorted(
            backups_to_delete.items(),
            key=lambda backup_item: backup_item[1].date,
        ):
            for agent_id in backup.agents:
                backups_to_delete_by_agent[agent_id][backup_id] = backup
        LOGGER.debug(
            "Backups returned by delete filter by agent: %s",
            {
                agent_id: list(backups)
                for agent_id, backups in backups_to_delete_by_agent.items()
            },
        )
        for agent_id, to_delete_from_agent in backups_to_delete_by_agent.items():
            if len(to_delete_from_agent) >= len(backups_by_agent[agent_id]):
                # Never delete the last backup.
                last_backup = to_delete_from_agent.popitem()
                LOGGER.debug(
                    "Keeping the last backup %s for agent %s", last_backup, agent_id
                )

        LOGGER.debug(
            "Backups to delete by agent: %s",
            {
                agent_id: list(backups)
                for agent_id, backups in backups_to_delete_by_agent.items()
            },
        )

        backup_ids_to_delete: dict[str, set[str]] = defaultdict(set)
        for agent_id, to_delete in backups_to_delete_by_agent.items():
            for backup_id in to_delete:
                backup_ids_to_delete[backup_id].add(agent_id)

        if not backup_ids_to_delete:
            return

        backup_ids = list(backup_ids_to_delete)
        delete_results = await asyncio.gather(
            *(
                self.async_delete_backup(backup_id, agent_ids=list(agent_ids))
                for backup_id, agent_ids in backup_ids_to_delete.items()
            )
        )
        agent_errors = {
            backup_id: error
            for backup_id, error in zip(backup_ids, delete_results, strict=True)
            if error and not isinstance(error, BackupNotFound)
        }
        if agent_errors:
            LOGGER.error(
                "Error deleting old copies: %s",
                agent_errors,
            )

    async def async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        contents: aiohttp.BodyPartReader,
    ) -> str:
        """Receive and store a backup file from upload."""
        if self.state is not BackupManagerState.IDLE:
            raise BackupManagerError(f"Backup manager busy: {self.state}")
        self.async_on_backup_event(
            ReceiveBackupEvent(
                reason=None,
                stage=None,
                state=ReceiveBackupState.IN_PROGRESS,
            )
        )
        try:
            backup_id = await self._async_receive_backup(
                agent_ids=agent_ids, contents=contents
            )
        except Exception:
            self.async_on_backup_event(
                ReceiveBackupEvent(
                    reason="unknown_error",
                    stage=None,
                    state=ReceiveBackupState.FAILED,
                )
            )
            raise
        else:
            self.async_on_backup_event(
                ReceiveBackupEvent(
                    reason=None,
                    stage=None,
                    state=ReceiveBackupState.COMPLETED,
                )
            )
            return backup_id
        finally:
            self.async_on_backup_event(IdleEvent())

    async def _async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        contents: aiohttp.BodyPartReader,
    ) -> str:
        """Receive and store a backup file from upload."""
        contents.chunk_size = BUF_SIZE
        self.async_on_backup_event(
            ReceiveBackupEvent(
                reason=None,
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
                reason=None,
                stage=ReceiveBackupStage.UPLOAD_TO_AGENTS,
                state=ReceiveBackupState.IN_PROGRESS,
            )
        )
        agent_errors = await self._async_upload_backup(
            backup=written_backup.backup,
            agent_ids=agent_ids,
            open_stream=written_backup.open_stream,
            # When receiving a backup, we don't decrypt or encrypt it according to the
            # agent settings, we just upload it as is.
            password=None,
        )
        await written_backup.release_stream()
        self.known_backups.add(written_backup.backup, agent_errors, [])
        return written_backup.backup.backup_id

    async def async_create_backup(
        self,
        *,
        agent_ids: list[str],
        extra_metadata: dict[str, bool | str] | None = None,
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        name: str | None,
        password: str | None,
        with_automatic_settings: bool = False,
    ) -> NewBackup:
        """Create a backup."""
        new_backup = await self.async_initiate_backup(
            agent_ids=agent_ids,
            extra_metadata=extra_metadata,
            include_addons=include_addons,
            include_all_addons=include_all_addons,
            include_database=include_database,
            include_folders=include_folders,
            include_homeassistant=include_homeassistant,
            name=name,
            password=password,
            raise_task_error=True,
            with_automatic_settings=with_automatic_settings,
        )
        assert self._backup_finish_task
        await self._backup_finish_task
        return new_backup

    async def async_create_automatic_backup(self) -> NewBackup:
        """Create a backup with automatic backup settings."""
        config_data = self.config.data
        return await self.async_create_backup(
            agent_ids=config_data.create_backup.agent_ids,
            include_addons=config_data.create_backup.include_addons,
            include_all_addons=config_data.create_backup.include_all_addons,
            include_database=config_data.create_backup.include_database,
            include_folders=config_data.create_backup.include_folders,
            include_homeassistant=True,  # always include HA
            name=config_data.create_backup.name,
            password=config_data.create_backup.password,
            with_automatic_settings=True,
        )

    async def async_initiate_backup(
        self,
        *,
        agent_ids: list[str],
        extra_metadata: dict[str, bool | str] | None = None,
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        name: str | None,
        password: str | None,
        raise_task_error: bool = False,
        with_automatic_settings: bool = False,
    ) -> NewBackup:
        """Initiate generating a backup."""
        if self.state is not BackupManagerState.IDLE:
            raise BackupManagerError(f"Backup manager busy: {self.state}")

        if with_automatic_settings:
            self.config.data.last_attempted_automatic_backup = dt_util.now()
            self.store.save()

        self.async_on_backup_event(
            CreateBackupEvent(
                reason=None,
                stage=None,
                state=CreateBackupState.IN_PROGRESS,
            )
        )
        try:
            return await self._async_create_backup(
                agent_ids=agent_ids,
                extra_metadata=extra_metadata,
                include_addons=include_addons,
                include_all_addons=include_all_addons,
                include_database=include_database,
                include_folders=include_folders,
                include_homeassistant=include_homeassistant,
                name=name,
                password=password,
                raise_task_error=raise_task_error,
                with_automatic_settings=with_automatic_settings,
            )
        except Exception as err:
            reason = err.error_code if isinstance(err, BackupError) else "unknown_error"
            self.async_on_backup_event(
                CreateBackupEvent(
                    reason=reason,
                    stage=None,
                    state=CreateBackupState.FAILED,
                )
            )
            self.async_on_backup_event(IdleEvent())
            if with_automatic_settings:
                self._update_issue_backup_failed()
            raise

    async def _async_create_backup(
        self,
        *,
        agent_ids: list[str],
        extra_metadata: dict[str, bool | str] | None,
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        name: str | None,
        password: str | None,
        raise_task_error: bool,
        with_automatic_settings: bool,
    ) -> NewBackup:
        """Initiate generating a backup."""
        unavailable_agents = [
            agent_id for agent_id in agent_ids if agent_id not in self.backup_agents
        ]
        if not (
            available_agents := [
                agent_id for agent_id in agent_ids if agent_id in self.backup_agents
            ]
        ):
            raise BackupManagerError(
                f"At least one available backup agent must be selected, got {agent_ids}"
            )
        if unavailable_agents:
            LOGGER.warning(
                "Backup agents %s are not available, will backupp to %s",
                unavailable_agents,
                available_agents,
            )
        if include_all_addons and include_addons:
            raise BackupManagerError(
                "Cannot include all addons and specify specific addons"
            )

        backup_name = (
            (name if name is None else name.strip())
            or f"{'Automatic' if with_automatic_settings else 'Custom'} backup {HAVERSION}"
        )
        extra_metadata = extra_metadata or {}

        try:
            (
                new_backup,
                self._backup_task,
            ) = await self._reader_writer.async_create_backup(
                agent_ids=available_agents,
                backup_name=backup_name,
                extra_metadata=extra_metadata
                | {
                    "instance_id": await instance_id.async_get(self.hass),
                    "with_automatic_settings": with_automatic_settings,
                },
                include_addons=include_addons,
                include_all_addons=include_all_addons,
                include_database=include_database,
                include_folders=include_folders,
                include_homeassistant=include_homeassistant,
                on_progress=self.async_on_backup_event,
                password=password,
            )
        except BackupReaderWriterError as err:
            raise BackupManagerError(str(err)) from err

        backup_finish_task = self._backup_finish_task = self.hass.async_create_task(
            self._async_finish_backup(
                available_agents, unavailable_agents, with_automatic_settings, password
            ),
            name="backup_manager_finish_backup",
        )
        if not raise_task_error:

            def log_finish_task_error(task: asyncio.Task[None]) -> None:
                if task.done() and not task.cancelled() and (err := task.exception()):
                    if isinstance(err, BackupManagerError):
                        LOGGER.error("Error creating backup: %s", err)
                    else:
                        LOGGER.error("Unexpected error: %s", err, exc_info=err)

            backup_finish_task.add_done_callback(log_finish_task_error)

        return new_backup

    async def _async_finish_backup(
        self,
        available_agents: list[str],
        unavailable_agents: list[str],
        with_automatic_settings: bool,
        password: str | None,
    ) -> None:
        """Finish a backup."""
        if TYPE_CHECKING:
            assert self._backup_task is not None
        backup_success = False
        try:
            written_backup = await self._backup_task
        except Exception as err:
            if with_automatic_settings:
                self._update_issue_backup_failed()

            if isinstance(err, BackupReaderWriterError):
                raise BackupManagerError(str(err)) from err
            raise  # unexpected error
        else:
            LOGGER.debug(
                "Generated new backup with backup_id %s, uploading to agents %s",
                written_backup.backup.backup_id,
                available_agents,
            )
            self.async_on_backup_event(
                CreateBackupEvent(
                    reason=None,
                    stage=CreateBackupStage.UPLOAD_TO_AGENTS,
                    state=CreateBackupState.IN_PROGRESS,
                )
            )

            try:
                agent_errors = await self._async_upload_backup(
                    backup=written_backup.backup,
                    agent_ids=available_agents,
                    open_stream=written_backup.open_stream,
                    password=password,
                )
            finally:
                await written_backup.release_stream()
            self.known_backups.add(
                written_backup.backup, agent_errors, unavailable_agents
            )
            if not agent_errors:
                if with_automatic_settings:
                    # create backup was successful, update last_completed_automatic_backup
                    self.config.data.last_completed_automatic_backup = dt_util.now()
                    self.store.save()
                backup_success = True

            if with_automatic_settings:
                self._update_issue_after_agent_upload(agent_errors, unavailable_agents)
            # delete old backups more numerous than copies
            # try this regardless of agent errors above
            await delete_backups_exceeding_configured_count(self)

        finally:
            self._backup_task = None
            self._backup_finish_task = None
            if backup_success:
                self.async_on_backup_event(
                    CreateBackupEvent(
                        reason=None,
                        stage=None,
                        state=CreateBackupState.COMPLETED,
                    )
                )
            else:
                self.async_on_backup_event(
                    CreateBackupEvent(
                        reason="upload_failed",
                        stage=None,
                        state=CreateBackupState.FAILED,
                    )
                )
            self.async_on_backup_event(IdleEvent())

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
            raise BackupManagerError(f"Backup manager busy: {self.state}")

        self.async_on_backup_event(
            RestoreBackupEvent(
                reason=None,
                stage=None,
                state=RestoreBackupState.IN_PROGRESS,
            )
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
            self.async_on_backup_event(
                RestoreBackupEvent(
                    reason=None,
                    stage=None,
                    state=RestoreBackupState.COMPLETED,
                )
            )
        except BackupError as err:
            self.async_on_backup_event(
                RestoreBackupEvent(
                    reason=err.error_code,
                    stage=None,
                    state=RestoreBackupState.FAILED,
                )
            )
            raise
        except Exception:
            self.async_on_backup_event(
                RestoreBackupEvent(
                    reason="unknown_error",
                    stage=None,
                    state=RestoreBackupState.FAILED,
                )
            )
            raise
        finally:
            self.async_on_backup_event(IdleEvent())

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
        try:
            backup = await agent.async_get_backup(backup_id)
        except BackupNotFound as err:
            raise BackupManagerError(
                f"Backup {backup_id} not found in agent {agent_id}"
            ) from err
        # Check for None to be backwards compatible with the old BackupAgent API,
        # this can be removed in HA Core 2025.10
        if not backup:
            frame.report_usage(
                "returns None from BackupAgent.async_get_backup",
                breaks_in_ha_version="2025.10",
                integration_domain=agent_id.partition(".")[0],
            )
            raise BackupManagerError(
                f"Backup {backup_id} not found in agent {agent_id}"
            )

        async def open_backup() -> AsyncIterator[bytes]:
            return await agent.async_download_backup(backup_id)

        await self._reader_writer.async_restore_backup(
            backup_id=backup_id,
            open_stream=open_backup,
            agent_id=agent_id,
            on_progress=self.async_on_backup_event,
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
        if (current_state := self.state) != (new_state := event.manager_state):
            LOGGER.debug("Backup state: %s -> %s", current_state, new_state)
        self.last_event = event
        if not isinstance(event, (BlockedEvent, IdleEvent)):
            self.last_action_event = event
        for subscription in self._backup_event_subscriptions:
            subscription(event)

    def _update_issue_backup_failed(self) -> None:
        """Update issue registry when a backup fails."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "automatic_backup_failed",
            is_fixable=False,
            is_persistent=True,
            learn_more_url="homeassistant://config/backup",
            severity=ir.IssueSeverity.WARNING,
            translation_key="automatic_backup_failed_create",
        )

    def _update_issue_after_agent_upload(
        self, agent_errors: dict[str, Exception], unavailable_agents: list[str]
    ) -> None:
        """Update issue registry after a backup is uploaded to agents."""
        if not agent_errors and not unavailable_agents:
            ir.async_delete_issue(self.hass, DOMAIN, "automatic_backup_failed")
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "automatic_backup_failed",
            is_fixable=False,
            is_persistent=True,
            learn_more_url="homeassistant://config/backup",
            severity=ir.IssueSeverity.WARNING,
            translation_key="automatic_backup_failed_upload_agents",
            translation_placeholders={
                "failed_agents": ", ".join(
                    chain(
                        (
                            self.backup_agents[agent_id].name
                            for agent_id in agent_errors
                        ),
                        unavailable_agents,
                    )
                )
            },
        )

    async def async_can_decrypt_on_download(
        self,
        backup_id: str,
        *,
        agent_id: str,
        password: str | None,
    ) -> None:
        """Check if we are able to decrypt the backup on download."""
        try:
            agent = self.backup_agents[agent_id]
        except KeyError as err:
            raise BackupManagerError(f"Invalid agent selected: {agent_id}") from err
        try:
            backup = await agent.async_get_backup(backup_id)
        except BackupNotFound as err:
            raise BackupManagerError(
                f"Backup {backup_id} not found in agent {agent_id}"
            ) from err
        # Check for None to be backwards compatible with the old BackupAgent API,
        # this can be removed in HA Core 2025.10
        if not backup:
            frame.report_usage(
                "returns None from BackupAgent.async_get_backup",
                breaks_in_ha_version="2025.10",
                integration_domain=agent_id.partition(".")[0],
            )
            raise BackupManagerError(
                f"Backup {backup_id} not found in agent {agent_id}"
            )
        reader: IO[bytes]
        if agent_id in self.local_backup_agents:
            local_agent = self.local_backup_agents[agent_id]
            path = local_agent.get_backup_path(backup_id)
            reader = await self.hass.async_add_executor_job(open, path.as_posix(), "rb")
        else:
            backup_stream = await agent.async_download_backup(backup_id)
            reader = cast(IO[bytes], AsyncIteratorReader(self.hass, backup_stream))
        try:
            await self.hass.async_add_executor_job(
                validate_password_stream, reader, password
            )
        except backup_util.IncorrectPassword as err:
            raise IncorrectPasswordError from err
        except backup_util.UnsupportedSecureTarVersion as err:
            raise DecryptOnDowloadNotSupported from err
        except backup_util.DecryptError as err:
            raise BackupManagerError(str(err)) from err
        finally:
            reader.close()


class KnownBackups:
    """Track known backups."""

    def __init__(self, manager: BackupManager) -> None:
        """Initialize."""
        self._backups: dict[str, KnownBackup] = {}
        self._manager = manager

    def load(self, stored_backups: list[StoredKnownBackup]) -> None:
        """Load backups."""
        self._backups = {
            backup["backup_id"]: KnownBackup(
                backup_id=backup["backup_id"],
                failed_agent_ids=backup["failed_agent_ids"],
            )
            for backup in stored_backups
        }

    def to_list(self) -> list[StoredKnownBackup]:
        """Convert known backups to a dict."""
        return [backup.to_dict() for backup in self._backups.values()]

    def add(
        self,
        backup: AgentBackup,
        agent_errors: dict[str, Exception],
        unavailable_agents: list[str],
    ) -> None:
        """Add a backup."""
        self._backups[backup.backup_id] = KnownBackup(
            backup_id=backup.backup_id,
            failed_agent_ids=list(chain(agent_errors, unavailable_agents)),
        )
        self._manager.store.save()

    def get(self, backup_id: str) -> KnownBackup | None:
        """Get a backup."""
        return self._backups.get(backup_id)

    def remove(self, backup_id: str) -> None:
        """Remove a backup."""
        if backup_id not in self._backups:
            return
        self._backups.pop(backup_id)
        self._manager.store.save()


@dataclass(kw_only=True)
class KnownBackup:
    """Persistent backup data."""

    backup_id: str
    failed_agent_ids: list[str]

    def to_dict(self) -> StoredKnownBackup:
        """Convert known backup to a dict."""
        return {
            "backup_id": self.backup_id,
            "failed_agent_ids": self.failed_agent_ids,
        }


class StoredKnownBackup(TypedDict):
    """Stored persistent backup data."""

    backup_id: str
    failed_agent_ids: list[str]


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
        extra_metadata: dict[str, bool | str],
        include_addons: list[str] | None,
        include_all_addons: bool,
        include_database: bool,
        include_folders: list[Folder] | None,
        include_homeassistant: bool,
        on_progress: Callable[[CreateBackupEvent], None],
        password: str | None,
    ) -> tuple[NewBackup, asyncio.Task[WrittenBackup]]:
        """Initiate generating a backup."""
        date_str = dt_util.now().isoformat()
        backup_id = _generate_backup_id(date_str, backup_name)

        if include_addons or include_all_addons or include_folders:
            raise BackupReaderWriterError(
                "Addons and folders are not supported by core backup"
            )
        if not include_homeassistant:
            raise BackupReaderWriterError("Home Assistant must be included in backup")

        backup_task = self._hass.async_create_task(
            self._async_create_backup(
                agent_ids=agent_ids,
                backup_id=backup_id,
                backup_name=backup_name,
                extra_metadata=extra_metadata,
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
        extra_metadata: dict[str, bool | str],
        include_database: bool,
        on_progress: Callable[[CreateBackupEvent], None],
        password: str | None,
    ) -> WrittenBackup:
        """Generate a backup."""
        manager = self._hass.data[DATA_MANAGER]

        agent_config = manager.config.data.agents.get(self._local_agent_id)
        if (
            self._local_agent_id in agent_ids
            and agent_config
            and not agent_config.protected
        ):
            password = None

        backup = AgentBackup(
            addons=[],
            backup_id=backup_id,
            database_included=include_database,
            date=date_str,
            extra_metadata=extra_metadata,
            folders=[],
            homeassistant_included=True,
            homeassistant_version=HAVERSION,
            name=backup_name,
            protected=password is not None,
            size=0,
        )

        local_agent_tar_file_path = None
        if self._local_agent_id in agent_ids:
            local_agent = manager.local_backup_agents[self._local_agent_id]
            local_agent_tar_file_path = local_agent.get_new_backup_path(backup)

        on_progress(
            CreateBackupEvent(
                reason=None,
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
                "extra": extra_metadata,
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
                local_agent_tar_file_path,
            )
        except (BackupManagerError, OSError, tarfile.TarError, ValueError) as err:
            # BackupManagerError from async_pre_backup_actions
            # OSError from file operations
            # TarError from tarfile
            # ValueError from json_bytes
            raise BackupReaderWriterError(str(err)) from err
        else:
            backup = replace(backup, size=size_in_bytes)

            async_add_executor_job = self._hass.async_add_executor_job

            async def send_backup() -> AsyncIterator[bytes]:
                try:
                    f = await async_add_executor_job(tar_file_path.open, "rb")
                    try:
                        while chunk := await async_add_executor_job(f.read, 2**20):
                            yield chunk
                    finally:
                        await async_add_executor_job(f.close)
                except OSError as err:
                    raise BackupReaderWriterError(str(err)) from err

            async def open_backup() -> AsyncIterator[bytes]:
                return send_backup()

            async def remove_backup() -> None:
                if local_agent_tar_file_path:
                    return
                try:
                    await async_add_executor_job(tar_file_path.unlink, True)
                except OSError as err:
                    raise BackupReaderWriterError(str(err)) from err

            return WrittenBackup(
                backup=backup, open_stream=open_backup, release_stream=remove_backup
            )
        finally:
            # Inform integrations the backup is done
            # If there's an unhandled exception, we keep it so we can rethrow it in case
            # the post backup actions also fail.
            unhandled_exc = sys.exception()
            try:
                try:
                    await manager.async_post_backup_actions()
                except BackupManagerError as err:
                    raise BackupReaderWriterError(str(err)) from err
            except Exception as err:
                if not unhandled_exc:
                    raise
                # If there's an unhandled exception, we wrap both that and the exception
                # from the post backup actions in an ExceptionGroup so the caller is
                # aware of both exceptions.
                raise BackupManagerExceptionGroup(
                    f"Multiple errors when creating backup: {unhandled_exc}, {err}",
                    [unhandled_exc, err],
                ) from None

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
        try:
            make_backup_dir(tar_file_path.parent)
        except OSError as err:
            raise BackupReaderWriterError(
                f"Failed to create dir {tar_file_path.parent}: "
                f"{err} ({err.__class__.__name__})"
            ) from err

        excludes = EXCLUDE_FROM_BACKUP
        if not database_included:
            excludes = excludes + EXCLUDE_DATABASE_FROM_BACKUP

        def is_excluded_by_filter(path: PurePath) -> bool:
            """Filter to filter excludes."""

            for exclude in excludes:
                # The home assistant core configuration directory is added as "data"
                # in the tar file, so we need to prefix that path to the filters.
                if not path.full_match(f"data/{exclude}"):
                    continue
                LOGGER.debug("Ignoring %s because of %s", path, exclude)
                return True

            return False

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
                    file_filter=is_excluded_by_filter,
                    arcname="data",
                )
        try:
            stat_result = tar_file_path.stat()
        except OSError as err:
            raise BackupReaderWriterError(
                f"Error getting size of {tar_file_path}: "
                f"{err} ({err.__class__.__name__})"
            ) from err
        return (tar_file_path, stat_result.st_size)

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
            tar_file_path = local_agent.get_new_backup_path(backup)
            await async_add_executor_job(make_backup_dir, tar_file_path.parent)
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
        on_progress: Callable[[RestoreBackupEvent], None],
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
            raise BackupReaderWriterError(
                "Addons and folders are not supported in core restore"
            )
        if not restore_homeassistant and not restore_database:
            raise BackupReaderWriterError(
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

        password_valid = await self._hass.async_add_executor_job(
            validate_password, path, password
        )
        if not password_valid:
            raise IncorrectPasswordError

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
        on_progress(
            RestoreBackupEvent(
                reason=None,
                stage=None,
                state=RestoreBackupState.CORE_RESTART,
            )
        )
        await self._hass.services.async_call("homeassistant", "restart", blocking=True)

    async def async_resume_restore_progress_after_restart(
        self,
        *,
        on_progress: Callable[[RestoreBackupEvent | IdleEvent], None],
    ) -> None:
        """Check restore status after core restart."""

        def _read_restore_file() -> json_util.JsonObjectType | None:
            """Read the restore file."""
            result_path = Path(self._hass.config.path(RESTORE_BACKUP_RESULT_FILE))

            try:
                restore_result = json_util.json_loads_object(result_path.read_bytes())
            except FileNotFoundError:
                return None
            finally:
                try:
                    result_path.unlink(missing_ok=True)
                except OSError as err:
                    LOGGER.warning(
                        "Unexpected error deleting backup restore result file: %s %s",
                        type(err),
                        err,
                    )

            return restore_result

        restore_result = await self._hass.async_add_executor_job(_read_restore_file)
        if not restore_result:
            return

        success = restore_result["success"]
        if not success:
            LOGGER.warning(
                "Backup restore failed with %s: %s",
                restore_result["error_type"],
                restore_result["error"],
            )
        state = RestoreBackupState.COMPLETED if success else RestoreBackupState.FAILED
        on_progress(
            RestoreBackupEvent(
                reason=cast(str, restore_result["error"]),
                stage=None,
                state=state,
            )
        )
        on_progress(IdleEvent())

    async def async_validate_config(self, *, config: BackupConfig) -> None:
        """Validate backup config.

        Update automatic backup settings to not include addons or folders and remove
        hassio agents in case a backup created by supervisor was restored.
        """
        create_backup = config.data.create_backup
        if (
            not create_backup.include_addons
            and not create_backup.include_all_addons
            and not create_backup.include_folders
            and not any(a_id.startswith("hassio.") for a_id in create_backup.agent_ids)
        ):
            LOGGER.debug("Backup settings don't need to be adjusted")
            return

        LOGGER.info(
            "Adjusting backup settings to not include addons, folders or supervisor locations"
        )
        automatic_agents = [
            agent_id
            for agent_id in create_backup.agent_ids
            if not agent_id.startswith("hassio.")
        ]
        if (
            self._local_agent_id not in automatic_agents
            and "hassio.local" in create_backup.agent_ids
        ):
            automatic_agents = [self._local_agent_id, *automatic_agents]
        config.update(
            create_backup=CreateBackupParametersDict(
                agent_ids=automatic_agents,
                include_addons=None,
                include_all_addons=False,
                include_folders=None,
            )
        )


def _generate_backup_id(date: str, name: str) -> str:
    """Generate a backup ID."""
    return hashlib.sha1(f"{date} - {name}".lower().encode()).hexdigest()[:8]
