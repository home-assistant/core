"""Support for OneDrive backup."""

from collections.abc import AsyncIterator, Callable, Coroutine
from datetime import UTC, datetime, timedelta
import json
import logging
from typing import Any

from kiota_abstractions.api_error import APIError
from msgraph.generated.drives.item.items.item.create_upload_session.create_upload_session_post_request_body import (
    CreateUploadSessionPostRequestBody,
)
from msgraph.generated.models.drive_item_uploadable_properties import (
    DriveItemUploadableProperties,
)
from msgraph_core.models import LargeFileUploadSession
from msgraph_core.tasks import LargeFileUploadTask

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback

from . import OneDriveConfigEntry
from .const import CONF_BACKUP_FOLDER, DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .util import (
    async_iterator_to_bytesio,
    bytes_to_async_iterator,
    parse_backup_metadata,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[OneDriveConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    return [OneDriveBackupAgent(hass, entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed."""
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)

    return remove_listener


class OneDriveBackupAgent(BackupAgent):
    """OneDrive backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
        """Initialize the OneDrive backup agent."""
        super().__init__()
        self._graph_client = entry.runtime_data
        self._drive_item = self._graph_client.drives.by_drive_id(entry.unique_id)
        self._backup_folder = f"root:/{str(entry.data[CONF_BACKUP_FOLDER]).strip('/')}"
        self.name = entry.title
        self._hass = hass

    def _get_file_path(self, backup_id: str) -> str:
        """Return the file path for a backup."""
        return f"{self._backup_folder}/{backup_id}.tar:"

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        content = await self._drive_item.items.by_drive_item_id(
            self._get_file_path(backup_id)
        ).content.get()
        if content is None:
            raise BackupAgentError("Failed to download backup")
        return bytes_to_async_iterator(content)

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        backup_dict = backup.as_dict()

        if backup.folders:
            backup_dict["folders"] = json.dumps(backup.folders)

        if backup.addons:
            backup_dict["addons"] = json.dumps(backup.addons)

        if backup.extra_metadata:
            backup_dict["extra_metadata"] = json.dumps(backup.extra_metadata)

        upload_session_request_body = CreateUploadSessionPostRequestBody(
            item=DriveItemUploadableProperties(
                additional_data={
                    "@microsoft.graph.conflictBehavior": "fail",
                    # "description": json.dumps(backup_dict),
                    # "name": f"{backup.backup_id}.tar",
                }
            )
        )
        # small file upload -> works
        # await self._drive_item.items.by_drive_item_id(
        #     self._get_file_path("test")
        # ).content.put(body=b"Hello world")
        upload_session = await self._drive_item.items.by_drive_item_id(
            self._get_file_path(backup.backup_id)
        ).create_upload_session.post(upload_session_request_body)

        if upload_session is None:
            raise BackupAgentError("Failed to create upload session")

        large_file_upload_session = LargeFileUploadSession(
            upload_url=upload_session.upload_url,
            expiration_date_time=datetime.now(UTC) + timedelta(days=1),
            additional_data=upload_session.additional_data,
            next_expected_ranges=upload_session.next_expected_ranges,
        )

        task = LargeFileUploadTask(
            upload_session=large_file_upload_session,
            request_adapter=self._graph_client.request_adapter,
            stream=await async_iterator_to_bytesio(await open_stream()),
        )

        def progress_callback(uploaded_byte_range: tuple[int, int]):
            _LOGGER.warning(
                "Uploaded %s bytes of %s bytes of backup %s",
                uploaded_byte_range[0],
                backup.size,
                backup.name,
            )

        try:
            await task.upload(progress_callback)
        except APIError as err:
            _LOGGER.exception(
                "Error during upload: %s, %s", err.response_status_code, err.message
            )
            raise BackupAgentError("Upload failed") from err

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        await self._drive_item.items.by_drive_item_id(
            self._get_file_path(backup_id)
        ).delete()

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []
        items = await self._drive_item.items.by_drive_item_id(
            f"{self._backup_folder}:"
        ).children.get()
        if items and (values := items.value):
            for item in values:
                description = item.description
                if description is None:
                    continue
                if "homeassistant_version" in description:
                    backups.append(parse_backup_metadata(description))
        return backups

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        blob_properties = await self._drive_item.items.by_drive_item_id(
            self._get_file_path(backup_id)
        ).get()
        if blob_properties is None:
            raise BackupAgentError("Backup not found")
        return parse_backup_metadata(blob_properties.description)
