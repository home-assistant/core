"""Backup functionality for supervised installations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine, Mapping
from contextlib import suppress
import logging
import os
from pathlib import Path, PurePath
from typing import Any, cast
from uuid import UUID

from aiohasupervisor import SupervisorClient
from aiohasupervisor.exceptions import (
    SupervisorBadRequestError,
    SupervisorError,
    SupervisorNotFoundError,
)
from aiohasupervisor.models import (
    backups as supervisor_backups,
    mounts as supervisor_mounts,
)
from aiohasupervisor.models.backups import LOCATION_CLOUD_BACKUP, LOCATION_LOCAL_STORAGE

from homeassistant.components.backup import (
    DATA_MANAGER,
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupConfig,
    BackupManagerError,
    BackupNotFound,
    BackupReaderWriter,
    BackupReaderWriterError,
    CreateBackupEvent,
    CreateBackupParametersDict,
    CreateBackupStage,
    CreateBackupState,
    Folder,
    IdleEvent,
    IncorrectPasswordError,
    ManagerBackup,
    NewBackup,
    RestoreBackupEvent,
    RestoreBackupStage,
    RestoreBackupState,
    WrittenBackup,
    suggested_filename as suggested_backup_filename,
    suggested_filename_from_name_date,
)
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.backup import async_get_manager as async_get_backup_manager
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from homeassistant.util.enum import try_parse_enum

from .const import DATA_CONFIG_STORE, DOMAIN, EVENT_SUPERVISOR_EVENT
from .handler import get_supervisor_client

MOUNT_JOBS = ("mount_manager_create_mount", "mount_manager_remove_mount")
RESTORE_JOB_ID_ENV = "SUPERVISOR_RESTORE_JOB_ID"
# Set on backups automatically created when updating an addon
TAG_ADDON_UPDATE = "supervisor.addon_update"
_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return the hassio backup agents."""
    client = get_supervisor_client(hass)
    mounts = await client.mounts.info()
    agents: list[BackupAgent] = [
        SupervisorBackupAgent(hass, "local", LOCATION_LOCAL_STORAGE)
    ]
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
    details: supervisor_backups.BackupComplete, location: str
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
    extra_metadata = details.extra or {}
    return AgentBackup(
        addons=addons,
        backup_id=details.slug,
        database_included=database_included,
        date=extra_metadata.get(
            "supervisor.backup_request_date", details.date.isoformat()
        ),
        extra_metadata=details.extra or {},
        folders=[Folder(folder) for folder in details.folders],
        homeassistant_included=homeassistant_included,
        homeassistant_version=details.homeassistant,
        name=details.name,
        protected=details.location_attributes[location].protected,
        size=details.location_attributes[location].size_bytes,
    )


class SupervisorBackupAgent(BackupAgent):
    """Backup agent for supervised installations."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, name: str, location: str) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self._hass = hass
        self._backup_dir = Path("/backups")
        self._client = get_supervisor_client(hass)
        self.name = self.unique_id = name
        self.location = location

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        try:
            return await self._client.backups.download_backup(
                backup_id,
                options=supervisor_backups.DownloadBackupOptions(
                    location=self.location
                ),
            )
        except SupervisorNotFoundError as err:
            raise BackupNotFound(f"Backup {backup_id} not found") from err

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        The upload will be skipped if the backup already exists in the agent's location.
        """
        with suppress(BackupNotFound):
            if await self.async_get_backup(backup.backup_id):
                _LOGGER.debug(
                    "Backup %s already exists in location %s",
                    backup.backup_id,
                    self.location,
                )
                return
        stream = await open_stream()
        upload_options = supervisor_backups.UploadBackupOptions(
            location={self.location},
            filename=PurePath(suggested_backup_filename(backup)),
        )
        await self._client.backups.upload_backup(
            stream,
            upload_options,
        )

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backup_list = await self._client.backups.list()
        result = []
        for backup in backup_list:
            if self.location not in backup.location_attributes:
                continue
            details = await self._client.backups.backup_info(backup.slug)
            result.append(_backup_details_to_agent_backup(details, self.location))
        return result

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        try:
            details = await self._client.backups.backup_info(backup_id)
        except SupervisorNotFoundError as err:
            raise BackupNotFound(f"Backup {backup_id} not found") from err
        if self.location not in details.location_attributes:
            raise BackupNotFound(f"Backup {backup_id} not found")
        return _backup_details_to_agent_backup(details, self.location)

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Remove a backup."""
        try:
            await self._client.backups.remove_backup(
                backup_id,
                options=supervisor_backups.RemoveBackupOptions(
                    location={self.location}
                ),
            )
        except SupervisorNotFoundError as err:
            raise BackupNotFound(f"Backup {backup_id} not found") from err


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
        if not include_homeassistant and include_database:
            raise HomeAssistantError(
                "Cannot create a backup with database but without Home Assistant"
            )
        manager = self._hass.data[DATA_MANAGER]

        include_addons_set: supervisor_backups.AddonSet | set[str] | None = None
        if include_all_addons:
            include_addons_set = supervisor_backups.AddonSet.ALL
        elif include_addons:
            include_addons_set = set(include_addons)
        include_folders_set = {
            supervisor_backups.Folder(folder) for folder in include_folders or []
        }
        # Always include SSL if Home Assistant is included
        if include_homeassistant:
            include_folders_set.add(supervisor_backups.Folder.SSL)

        hassio_agents: list[SupervisorBackupAgent] = [
            cast(SupervisorBackupAgent, manager.backup_agents[agent_id])
            for agent_id in agent_ids
            if manager.backup_agents[agent_id].domain == DOMAIN
        ]

        # Supervisor does not support creating backups spread across multiple
        # locations, where some locations are encrypted and some are not.
        # It's inefficient to let core do all the copying so we want to let
        # supervisor handle as much as possible.
        # Therefore, we split the locations into two lists: encrypted and decrypted.
        # The longest list will be sent to supervisor, and the remaining locations
        # will be handled by async_upload_backup.
        # If the lists are the same length, it does not matter which one we send,
        # we send the encrypted list to have a well defined behavior.
        encrypted_locations: list[str] = []
        decrypted_locations: list[str] = []
        agents_settings = manager.config.data.agents
        for hassio_agent in hassio_agents:
            if password is not None:
                if agent_settings := agents_settings.get(hassio_agent.agent_id):
                    if agent_settings.protected:
                        encrypted_locations.append(hassio_agent.location)
                    else:
                        decrypted_locations.append(hassio_agent.location)
                else:
                    encrypted_locations.append(hassio_agent.location)
            else:
                decrypted_locations.append(hassio_agent.location)
        _LOGGER.debug("Encrypted locations: %s", encrypted_locations)
        _LOGGER.debug("Decrypted locations: %s", decrypted_locations)
        if hassio_agents:
            if len(encrypted_locations) >= len(decrypted_locations):
                locations = encrypted_locations
            else:
                locations = decrypted_locations
                password = None
        else:
            locations = []
        locations = locations or [LOCATION_CLOUD_BACKUP]

        date = dt_util.now().isoformat()
        extra_metadata = extra_metadata | {"supervisor.backup_request_date": date}
        filename = suggested_filename_from_name_date(backup_name, date)
        try:
            backup = await self._client.backups.partial_backup(
                supervisor_backups.PartialBackupOptions(
                    addons=include_addons_set,
                    folders=include_folders_set,
                    homeassistant=include_homeassistant,
                    name=backup_name,
                    password=password,
                    compressed=True,
                    location=locations,
                    homeassistant_exclude_database=not include_database,
                    background=True,
                    extra=extra_metadata,
                    filename=PurePath(filename),
                )
            )
        except SupervisorError as err:
            raise BackupReaderWriterError(f"Error creating backup: {err}") from err
        backup_task = self._hass.async_create_task(
            self._async_wait_for_backup(
                backup,
                locations,
                on_progress=on_progress,
                remove_after_upload=locations == [LOCATION_CLOUD_BACKUP],
            ),
            name="backup_manager_create_backup",
            eager_start=False,  # To ensure the task is not started before we return
        )

        return (NewBackup(backup_job_id=backup.job_id.hex), backup_task)

    async def _async_wait_for_backup(
        self,
        backup: supervisor_backups.NewBackup,
        locations: list[str],
        *,
        on_progress: Callable[[CreateBackupEvent], None],
        remove_after_upload: bool,
    ) -> WrittenBackup:
        """Wait for a backup to complete."""
        backup_complete = asyncio.Event()
        backup_id: str | None = None
        create_errors: list[dict[str, str]] = []

        @callback
        def on_job_progress(data: Mapping[str, Any]) -> None:
            """Handle backup progress."""
            nonlocal backup_id
            if not (stage := try_parse_enum(CreateBackupStage, data.get("stage"))):
                _LOGGER.debug("Unknown create stage: %s", data.get("stage"))
            else:
                on_progress(
                    CreateBackupEvent(
                        reason=None, stage=stage, state=CreateBackupState.IN_PROGRESS
                    )
                )
            if data.get("done") is True:
                backup_id = data.get("reference")
                create_errors.extend(data.get("errors", []))
                backup_complete.set()

        unsub = self._async_listen_job_events(backup.job_id, on_job_progress)
        try:
            await self._get_job_state(backup.job_id, on_job_progress)
            await backup_complete.wait()
        finally:
            unsub()
        if not backup_id or create_errors:
            # We should add more specific error handling here in the future
            raise BackupReaderWriterError(
                f"Backup failed: {create_errors or 'no backup_id'}"
            )

        async def open_backup() -> AsyncIterator[bytes]:
            try:
                return await self._client.backups.download_backup(backup_id)
            except SupervisorError as err:
                raise BackupReaderWriterError(
                    f"Error downloading backup: {err}"
                ) from err

        async def remove_backup() -> None:
            if not remove_after_upload:
                return
            try:
                await self._client.backups.remove_backup(
                    backup_id,
                    options=supervisor_backups.RemoveBackupOptions(
                        location={LOCATION_CLOUD_BACKUP}
                    ),
                )
            except SupervisorError as err:
                raise BackupReaderWriterError(f"Error removing backup: {err}") from err

        try:
            details = await self._client.backups.backup_info(backup_id)
        except SupervisorError as err:
            raise BackupReaderWriterError(
                f"Error getting backup details: {err}"
            ) from err

        return WrittenBackup(
            backup=_backup_details_to_agent_backup(details, locations[0]),
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
        locations = [agent.location for agent in hassio_agents]
        locations = locations or [LOCATION_CLOUD_BACKUP]

        backup_id = await self._client.backups.upload_backup(
            stream,
            supervisor_backups.UploadBackupOptions(location=set(locations)),
        )

        async def open_backup() -> AsyncIterator[bytes]:
            return await self._client.backups.download_backup(backup_id)

        async def remove_backup() -> None:
            if locations != [LOCATION_CLOUD_BACKUP]:
                return
            await self._client.backups.remove_backup(
                backup_id,
                options=supervisor_backups.RemoveBackupOptions(
                    location={LOCATION_CLOUD_BACKUP}
                ),
            )

        details = await self._client.backups.backup_info(backup_id)

        return WrittenBackup(
            backup=_backup_details_to_agent_backup(details, locations[0]),
            open_stream=open_backup,
            release_stream=remove_backup,
        )

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
        manager = self._hass.data[DATA_MANAGER]
        # The backup manager has already checked that the backup exists so we don't
        # need to catch BackupNotFound here.
        backup = await manager.backup_agents[agent_id].async_get_backup(backup_id)
        if (
            # Check for None to be backwards compatible with the old BackupAgent API,
            # this can be removed in HA Core 2025.10
            backup
            and restore_homeassistant
            and restore_database != backup.database_included
        ):
            raise HomeAssistantError("Restore database must match backup")
        if not restore_homeassistant and restore_database:
            raise HomeAssistantError("Cannot restore database without Home Assistant")
        restore_addons_set = set(restore_addons) if restore_addons else None
        restore_folders_set = (
            {supervisor_backups.Folder(folder) for folder in restore_folders}
            if restore_folders
            else None
        )

        restore_location: str
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

        try:
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
        except SupervisorNotFoundError as err:
            raise BackupNotFound from err
        except SupervisorBadRequestError as err:
            # Supervisor currently does not transmit machine parsable error types
            message = err.args[0]
            if message.startswith("Invalid password for backup"):
                raise IncorrectPasswordError(message) from err
            raise HomeAssistantError(message) from err

        restore_complete = asyncio.Event()
        restore_errors: list[dict[str, str]] = []

        @callback
        def on_job_progress(data: Mapping[str, Any]) -> None:
            """Handle backup restore progress."""
            if not (stage := try_parse_enum(RestoreBackupStage, data.get("stage"))):
                _LOGGER.debug("Unknown restore stage: %s", data.get("stage"))
            else:
                on_progress(
                    RestoreBackupEvent(
                        reason=None, stage=stage, state=RestoreBackupState.IN_PROGRESS
                    )
                )
            if data.get("done") is True:
                restore_complete.set()
                restore_errors.extend(data.get("errors", []))

        unsub = self._async_listen_job_events(job.job_id, on_job_progress)
        try:
            await self._get_job_state(job.job_id, on_job_progress)
            await restore_complete.wait()
            if restore_errors:
                # We should add more specific error handling here in the future
                raise BackupReaderWriterError(f"Restore failed: {restore_errors}")
        finally:
            unsub()

    async def async_resume_restore_progress_after_restart(
        self,
        *,
        on_progress: Callable[[RestoreBackupEvent | IdleEvent], None],
    ) -> None:
        """Check restore status after core restart."""
        if not (restore_job_str := os.environ.get(RESTORE_JOB_ID_ENV)):
            _LOGGER.debug("No restore job ID found in environment")
            return

        restore_job_id = UUID(restore_job_str)
        _LOGGER.debug("Found restore job ID %s in environment", restore_job_id)

        sent_event = False

        @callback
        def on_job_progress(data: Mapping[str, Any]) -> None:
            """Handle backup restore progress."""
            nonlocal sent_event

            if not (stage := try_parse_enum(RestoreBackupStage, data.get("stage"))):
                _LOGGER.debug("Unknown restore stage: %s", data.get("stage"))

            if data.get("done") is not True:
                if stage or not sent_event:
                    sent_event = True
                    on_progress(
                        RestoreBackupEvent(
                            reason=None,
                            stage=stage,
                            state=RestoreBackupState.IN_PROGRESS,
                        )
                    )
                return

            restore_errors = data.get("errors", [])
            if restore_errors:
                _LOGGER.warning("Restore backup failed: %s", restore_errors)
                # We should add more specific error handling here in the future
                on_progress(
                    RestoreBackupEvent(
                        reason="unknown_error",
                        stage=stage,
                        state=RestoreBackupState.FAILED,
                    )
                )
            else:
                on_progress(
                    RestoreBackupEvent(
                        reason=None, stage=stage, state=RestoreBackupState.COMPLETED
                    )
                )
            on_progress(IdleEvent())
            unsub()

        unsub = self._async_listen_job_events(restore_job_id, on_job_progress)
        try:
            await self._get_job_state(restore_job_id, on_job_progress)
        except SupervisorError as err:
            _LOGGER.debug("Could not get restore job %s: %s", restore_job_id, err)
            unsub()

    async def async_validate_config(self, *, config: BackupConfig) -> None:
        """Validate backup config.

        Replace the core backup agent with the hassio default agent.
        """
        core_agent_id = "backup.local"
        create_backup = config.data.create_backup
        if core_agent_id not in create_backup.agent_ids:
            _LOGGER.debug("Backup settings don't need to be adjusted")
            return

        default_agent = await _default_agent(self._client)
        _LOGGER.info("Adjusting backup settings to not include core backup location")
        automatic_agents = [
            agent_id if agent_id != core_agent_id else default_agent
            for agent_id in create_backup.agent_ids
        ]
        config.update(
            create_backup=CreateBackupParametersDict(agent_ids=automatic_agents)
        )

    @callback
    def _async_listen_job_events(
        self, job_id: UUID, on_event: Callable[[Mapping[str, Any]], None]
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
                or event_data.get("uuid") != job_id.hex
            ):
                return
            on_event(event_data)

        unsub_signal = async_dispatcher_connect(
            self._hass, EVENT_SUPERVISOR_EVENT, handle_signal
        )
        return unsub

    async def _get_job_state(
        self, job_id: UUID, on_event: Callable[[Mapping[str, Any]], None]
    ) -> None:
        """Poll a job for its state."""
        job = await self._client.jobs.get_job(job_id)
        _LOGGER.debug("Job state: %s", job)
        on_event(job.to_dict())


async def _default_agent(client: SupervisorClient) -> str:
    """Return the default agent for creating a backup."""
    mounts = await client.mounts.info()
    default_mount = mounts.default_backup_mount
    return f"hassio.{default_mount if default_mount is not None else 'local'}"


async def backup_addon_before_update(
    hass: HomeAssistant,
    addon: str,
    addon_name: str | None,
    installed_version: str | None,
) -> None:
    """Prepare for updating an add-on."""
    backup_manager = hass.data[DATA_MANAGER]
    client = get_supervisor_client(hass)

    # Use the password from automatic settings if available
    if backup_manager.config.data.create_backup.agent_ids:
        password = backup_manager.config.data.create_backup.password
    else:
        password = None

    def addon_update_backup_filter(
        backups: dict[str, ManagerBackup],
    ) -> dict[str, ManagerBackup]:
        """Return addon update backups."""
        return {
            backup_id: backup
            for backup_id, backup in backups.items()
            if backup.extra_metadata.get(TAG_ADDON_UPDATE) == addon
        }

    def _delete_filter(
        backups: dict[str, ManagerBackup],
    ) -> dict[str, ManagerBackup]:
        """Return oldest backups more numerous than copies to delete."""
        update_config = hass.data[DATA_CONFIG_STORE].data.update_config
        return dict(
            sorted(
                backups.items(),
                key=lambda backup_item: backup_item[1].date,
            )[: max(len(backups) - update_config.add_on_backup_retain_copies, 0)]
        )

    try:
        await backup_manager.async_create_backup(
            agent_ids=[await _default_agent(client)],
            extra_metadata={TAG_ADDON_UPDATE: addon},
            include_addons=[addon],
            include_all_addons=False,
            include_database=False,
            include_folders=None,
            include_homeassistant=False,
            name=f"{addon_name or addon} {installed_version or '<unknown>'}",
            password=password,
        )
    except BackupManagerError as err:
        raise HomeAssistantError(f"Error creating backup: {err}") from err
    else:
        try:
            await backup_manager.async_delete_filtered_backups(
                include_filter=addon_update_backup_filter,
                delete_filter=_delete_filter,
            )
        except BackupManagerError as err:
            raise HomeAssistantError(f"Error deleting old backups: {err}") from err


async def backup_core_before_update(hass: HomeAssistant) -> None:
    """Prepare for updating core."""
    backup_manager = await async_get_backup_manager(hass)
    client = get_supervisor_client(hass)

    try:
        if backup_manager.config.data.create_backup.agent_ids:
            # Create a backup with automatic settings
            await backup_manager.async_create_automatic_backup()
        else:
            # Create a manual backup
            await backup_manager.async_create_backup(
                agent_ids=[await _default_agent(client)],
                include_addons=None,
                include_all_addons=False,
                include_database=True,
                include_folders=None,
                include_homeassistant=True,
                name=f"Home Assistant Core {HAVERSION}",
                password=None,
            )
    except BackupManagerError as err:
        raise HomeAssistantError(f"Error creating backup: {err}") from err
