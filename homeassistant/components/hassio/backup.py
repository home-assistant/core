"""Backup functionality for supervised installations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine, Mapping
import logging
from pathlib import Path
from typing import Any, cast

from aiohasupervisor.exceptions import (
    SupervisorBadRequestError,
    SupervisorNotFoundError,
)
from aiohasupervisor.models import (
    backups as supervisor_backups,
    mounts as supervisor_mounts,
)

from homeassistant.components.backup import (
    DATA_MANAGER,
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupReaderWriter,
    CreateBackupEvent,
    Folder,
    NewBackup,
    WrittenBackup,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, EVENT_SUPERVISOR_EVENT
from .handler import get_supervisor_client

LOCATION_CLOUD_BACKUP = ".cloud_backup"
MOUNT_JOBS = ("mount_manager_create_mount", "mount_manager_remove_mount")
_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return the hassio backup agents."""
    client = get_supervisor_client(hass)
    mounts = await client.mounts.info()
    agents: list[BackupAgent] = [SupervisorBackupAgent(hass, "local", None)]
    for mount in mounts.mounts:
        if mount.usage is not supervisor_mounts.MountUsage.BACKUP:
            continue
        agents.append(SupervisorBackupAgent(hass, mount.name, mount.name))
    return agents


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed."""

    @callback
    def unsub() -> None:
        """Unsubscribe from job events."""
        unsub_signal()

    @callback
    def handle_signal(data: Mapping[str, Any]) -> None:
        """Handle a job signal."""
        if (
            data.get("event") != "job"
            or not (event_data := data.get("data"))
            or event_data.get("name") not in MOUNT_JOBS
            or event_data.get("done") is not True
        ):
            return
        _LOGGER.debug("Mount added or removed %s, calling listener", data)
        listener()

    unsub_signal = async_dispatcher_connect(hass, EVENT_SUPERVISOR_EVENT, handle_signal)
    return unsub


def _backup_details_to_agent_backup(
    details: supervisor_backups.BackupComplete,
) -> AgentBackup:
    """Convert a supervisor backup details object to an agent backup."""
    homeassistant_included = details.homeassistant is not None
    if not homeassistant_included:
        database_included = False
    else:
        database_included = details.homeassistant_exclude_database is False
    addons = [
        AddonInfo(name=addon.name, slug=addon.slug, version=addon.version)
        for addon in details.addons
    ]
    return AgentBackup(
        addons=addons,
        backup_id=details.slug,
        database_included=database_included,
        date=details.date.isoformat(),
        extra_metadata=details.extra or {},
        folders=[Folder(folder) for folder in details.folders],
        homeassistant_included=homeassistant_included,
        homeassistant_version=details.homeassistant,
        name=details.name,
        protected=details.protected,
        size=details.size_bytes,
    )


class SupervisorBackupAgent(BackupAgent):
    """Backup agent for supervised installations."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, name: str, location: str | None) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self._hass = hass
        self._backup_dir = Path("/backups")
        self._client = get_supervisor_client(hass)
        self.name = name
        self.location = location

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        return await self._client.backups.download_backup(
            backup_id,
            options=supervisor_backups.DownloadBackupOptions(location=self.location),
        )

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        Not required for supervisor, the SupervisorBackupReaderWriter stores files.
        """

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backup_list = await self._client.backups.list()
        result = []
        for backup in backup_list:
            if not backup.locations or self.location not in backup.locations:
                continue
            details = await self._client.backups.backup_info(backup.slug)
            result.append(_backup_details_to_agent_backup(details))
        return result

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        details = await self._client.backups.backup_info(backup_id)
        if self.location not in details.locations:
            return None
        return _backup_details_to_agent_backup(details)

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Remove a backup."""
        try:
            await self._client.backups.remove_backup(
                backup_id,
                options=supervisor_backups.RemoveBackupOptions(
                    location={self.location}
                ),
            )
        except SupervisorBadRequestError as err:
            if err.args[0] != "Backup does not exist":
                raise
            _LOGGER.debug("Backup %s does not exist", backup_id)
        except SupervisorNotFoundError:
            _LOGGER.debug("Backup %s does not exist", backup_id)


class SupervisorBackupReaderWriter(BackupReaderWriter):
    """Class for reading and writing backups in supervised installations."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup reader/writer."""
        self._hass = hass
        self._client = get_supervisor_client(hass)

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
        manager = self._hass.data[DATA_MANAGER]

        include_addons_set: supervisor_backups.AddonSet | set[str] | None = None
        if include_all_addons:
            include_addons_set = supervisor_backups.AddonSet.ALL
        elif include_addons:
            include_addons_set = set(include_addons)
        include_folders_set = (
            {supervisor_backups.Folder(folder) for folder in include_folders}
            if include_folders
            else None
        )

        hassio_agents: list[SupervisorBackupAgent] = [
            cast(SupervisorBackupAgent, manager.backup_agents[agent_id])
            for agent_id in agent_ids
            if manager.backup_agents[agent_id].domain == DOMAIN
        ]
        locations = [agent.location for agent in hassio_agents]

        backup = await self._client.backups.partial_backup(
            supervisor_backups.PartialBackupOptions(
                addons=include_addons_set,
                folders=include_folders_set,
                homeassistant=include_homeassistant,
                name=backup_name,
                password=password,
                compressed=True,
                location=locations or LOCATION_CLOUD_BACKUP,
                homeassistant_exclude_database=not include_database,
                background=True,
                extra=extra_metadata,
            )
        )
        backup_task = self._hass.async_create_task(
            self._async_wait_for_backup(
                backup, remove_after_upload=not bool(locations)
            ),
            name="backup_manager_create_backup",
            eager_start=False,  # To ensure the task is not started before we return
        )

        return (NewBackup(backup_job_id=backup.job_id), backup_task)

    async def _async_wait_for_backup(
        self, backup: supervisor_backups.NewBackup, *, remove_after_upload: bool
    ) -> WrittenBackup:
        """Wait for a backup to complete."""
        backup_complete = asyncio.Event()
        backup_id: str | None = None

        @callback
        def on_progress(data: Mapping[str, Any]) -> None:
            """Handle backup progress."""
            nonlocal backup_id
            if data.get("done") is True:
                backup_id = data.get("reference")
                backup_complete.set()

        try:
            unsub = self._async_listen_job_events(backup.job_id, on_progress)
            await backup_complete.wait()
        finally:
            unsub()
        if not backup_id:
            raise HomeAssistantError("Backup failed")

        async def open_backup() -> AsyncIterator[bytes]:
            return await self._client.backups.download_backup(backup_id)

        async def remove_backup() -> None:
            if not remove_after_upload:
                return
            await self._client.backups.remove_backup(
                backup_id,
                options=supervisor_backups.RemoveBackupOptions(
                    location={LOCATION_CLOUD_BACKUP}
                ),
            )

        details = await self._client.backups.backup_info(backup_id)

        return WrittenBackup(
            backup=_backup_details_to_agent_backup(details),
            open_stream=open_backup,
            release_stream=remove_backup,
        )

    async def async_receive_backup(
        self,
        *,
        agent_ids: list[str],
        stream: AsyncIterator[bytes],
        suggested_filename: str,
    ) -> WrittenBackup:
        """Receive a backup."""
        manager = self._hass.data[DATA_MANAGER]

        hassio_agents: list[SupervisorBackupAgent] = [
            cast(SupervisorBackupAgent, manager.backup_agents[agent_id])
            for agent_id in agent_ids
            if manager.backup_agents[agent_id].domain == DOMAIN
        ]
        locations = {agent.location for agent in hassio_agents}

        backup_id = await self._client.backups.upload_backup(
            stream,
            supervisor_backups.UploadBackupOptions(
                location=locations or {LOCATION_CLOUD_BACKUP}
            ),
        )

        async def open_backup() -> AsyncIterator[bytes]:
            return await self._client.backups.download_backup(backup_id)

        async def remove_backup() -> None:
            if locations:
                return
            await self._client.backups.remove_backup(
                backup_id,
                options=supervisor_backups.RemoveBackupOptions(
                    location={LOCATION_CLOUD_BACKUP}
                ),
            )

        details = await self._client.backups.backup_info(backup_id)

        return WrittenBackup(
            backup=_backup_details_to_agent_backup(details),
            open_stream=open_backup,
            release_stream=remove_backup,
        )

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
        if restore_homeassistant and not restore_database:
            raise HomeAssistantError("Cannot restore Home Assistant without database")
        if not restore_homeassistant and restore_database:
            raise HomeAssistantError("Cannot restore database without Home Assistant")
        restore_addons_set = set(restore_addons) if restore_addons else None
        restore_folders_set = (
            {supervisor_backups.Folder(folder) for folder in restore_folders}
            if restore_folders
            else None
        )

        manager = self._hass.data[DATA_MANAGER]
        restore_location: str | None
        if manager.backup_agents[agent_id].domain != DOMAIN:
            # Download the backup to the supervisor. Supervisor will clean up the backup
            # two days after the restore is done.
            await self.async_receive_backup(
                agent_ids=[],
                stream=await open_stream(),
                suggested_filename=f"{backup_id}.tar",
            )
            restore_location = LOCATION_CLOUD_BACKUP
        else:
            agent = cast(SupervisorBackupAgent, manager.backup_agents[agent_id])
            restore_location = agent.location

        job = await self._client.backups.partial_restore(
            backup_id,
            supervisor_backups.PartialRestoreOptions(
                addons=restore_addons_set,
                folders=restore_folders_set,
                homeassistant=restore_homeassistant,
                password=password,
                background=True,
                location=restore_location,
            ),
        )

        restore_complete = asyncio.Event()

        @callback
        def on_progress(data: Mapping[str, Any]) -> None:
            """Handle backup progress."""
            if data.get("done") is True:
                restore_complete.set()

        try:
            unsub = self._async_listen_job_events(job.job_id, on_progress)
            await restore_complete.wait()
        finally:
            unsub()

    @callback
    def _async_listen_job_events(
        self, job_id: str, on_event: Callable[[Mapping[str, Any]], None]
    ) -> Callable[[], None]:
        """Listen for job events."""

        @callback
        def unsub() -> None:
            """Unsubscribe from job events."""
            unsub_signal()

        @callback
        def handle_signal(data: Mapping[str, Any]) -> None:
            """Handle a job signal."""
            if (
                data.get("event") != "job"
                or not (event_data := data.get("data"))
                or event_data.get("uuid") != job_id
            ):
                return
            on_event(event_data)

        unsub_signal = async_dispatcher_connect(
            self._hass, EVENT_SUPERVISOR_EVENT, handle_signal
        )
        return unsub
