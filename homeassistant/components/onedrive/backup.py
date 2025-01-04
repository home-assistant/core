"""Support for OneDrive backup."""

from collections.abc import AsyncIterator, Callable, Coroutine
from datetime import datetime, timedelta
import json
import logging
from typing import Any

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
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .util import bytes_to_async_iterator, parse_backup_metadata

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
        self._graph_client = entry.runtime_data.graph_client
        self._drive_item = self._graph_client.drives.by_drive_id(
            entry.runtime_data.drive_id
        )
        self.name = entry.title
        self._hass = hass

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        item_id = await self._get_drive_item_from_name(f"{backup_id}.tar")
        content = await self._drive_item.items.by_drive_item_id(item_id).content.get()
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

        stream = await open_stream()

        uploadable_properties = DriveItemUploadableProperties(
            additional_data=backup_dict
        )
        upload_session_request_body = CreateUploadSessionPostRequestBody(
            item=uploadable_properties
        )
        upload_session = await self._drive_item.items.by_drive_item_id(
            f"{backup.backup_id}.tar"
        ).create_upload_session.post(upload_session_request_body)

        if upload_session is None:
            raise BackupAgentError("Failed to create upload session")

        large_file_upload_session = LargeFileUploadSession(
            upload_url=upload_session.upload_url,
            expiration_date_time=datetime.now() + timedelta(days=1),
            additional_data=upload_session.additional_data,
            is_cancelled=False,
            next_expected_ranges=upload_session.next_expected_ranges,
        )

        task = LargeFileUploadTask(
            large_file_upload_session, self._graph_client.request_adapter, stream=stream
        )
        await task.upload()

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        item_id = await self._get_drive_item_from_name(f"{backup_id}.tar")
        await self._drive_item.items.by_drive_item_id(item_id).delete()

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []
        items = await self._drive_item.items.get()
        if items and (values := items.value):
            for item in values:
                additional_data = item.additional_data
                if "homeassistant_version" in additional_data:
                    backups.append(parse_backup_metadata(additional_data))
        return backups

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        item_id = await self._get_drive_item_from_name(f"{backup_id}.tar")
        blob_properties = await self._drive_item.items.by_drive_item_id(item_id).get()
        if blob_properties is None:
            raise BackupAgentError("Backup not found")
        return parse_backup_metadata(blob_properties.additional_data)

    async def _get_drive_item_from_name(self, name: str) -> str:
        """Get a drive item by name."""
        item_id: str | None = None
        items = await self._drive_item.items.get()
        if items and (values := items.value):
            for item in values:
                if item.name == name:
                    item_id = item.id
        if item_id is None:
            raise BackupAgentError("Backup not found")
        return item_id
