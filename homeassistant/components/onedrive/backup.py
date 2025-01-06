"""Support for OneDrive backup."""

from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from functools import wraps
import json
import logging
from typing import Any, TypeVar

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import AnonymousAuthenticationProvider
from msgraph import GraphRequestAdapter
from msgraph.generated.drives.item.items.item.create_upload_session.create_upload_session_post_request_body import (
    CreateUploadSessionPostRequestBody,
)
from msgraph.generated.models.drive_item import DriveItem
from msgraph.generated.models.drive_item_uploadable_properties import (
    DriveItemUploadableProperties,
)
from msgraph_core.tasks import LargeFileUploadTask

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.httpx_client import get_async_client

from . import OneDriveConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .util import (
    async_iterator_to_bytesio,
    backup_from_description,
    bytes_to_async_iterator,
)

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T", bound=Callable[..., Awaitable[Any]])


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


def handle_backup_errors(func: _T) -> _T:
    """Handle backup errors."""

    @wraps(func)
    async def inner(*args: Any, **kwargs: Any):
        try:
            return await func(*args, **kwargs)
        except APIError as err:
            _LOGGER.error(
                "Error during backup in %s: Status %s, message %s",
                func.__name__,
                err.response_status_code,
                err.message,
            )
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(
                translation_domain=DOMAIN, translation_key="backup_failure"
            ) from err

    return inner


class OneDriveBackupAgent(BackupAgent):
    """OneDrive backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
        """Initialize the OneDrive backup agent."""
        super().__init__()
        self._items = entry.runtime_data.items
        self._folder_id = entry.runtime_data.folder_id
        self._anonymous_auth_adapter = GraphRequestAdapter(
            auth_provider=AnonymousAuthenticationProvider,
            client=get_async_client(hass),
        )
        self.name = entry.title

    @handle_backup_errors
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        content = await self._items.by_drive_item_id(
            f"{self._folder_id}:/{backup_id}.tar:"
        ).content.get()
        if content is None:
            raise BackupAgentError(
                translation_domain=DOMAIN, translation_key="backup_no_content"
            )
        return bytes_to_async_iterator(content)

    @handle_backup_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""

        # upload file in chunks to support large files
        upload_session_request_body = CreateUploadSessionPostRequestBody(
            item=DriveItemUploadableProperties(
                additional_data={
                    "@microsoft.graph.conflictBehavior": "fail",
                },
            )
        )
        upload_session = await self._items.by_drive_item_id(
            f"{self._folder_id}:/{backup.backup_id}.tar:"
        ).create_upload_session.post(upload_session_request_body)

        if upload_session is None:
            raise BackupAgentError(
                translation_domain=DOMAIN, translation_key="backup_no_upload_session"
            )

        task = LargeFileUploadTask(
            upload_session=upload_session,
            request_adapter=self._anonymous_auth_adapter,
            stream=await async_iterator_to_bytesio(await open_stream()),
            max_chunk_size=320 * 1024,
        )

        def progress_callback(uploaded_byte_range: tuple[int, int]) -> None:
            _LOGGER.debug(
                "Uploaded %s bytes of %s bytes of backup %s",
                uploaded_byte_range[0],
                backup.size,
                backup.name,
            )

        await task.upload(progress_callback)
        _LOGGER.debug("Backup %s uploaded", backup.name)

        # store metadata in description
        backup_dict = backup.as_dict()
        backup_dict["version"] = 1  # version of the backup metadata
        description = json.dumps(backup_dict)
        _LOGGER.debug("Creating metadata: %s", description)

        await self._items.by_drive_item_id(
            f"{self._folder_id}:/{backup.backup_id}.tar:"
        ).patch(DriveItem(description=description))

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        await self._items.by_drive_item_id(
            f"{self._folder_id}:/{backup_id}.tar:"
        ).delete()

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []
        items = await self._items.by_drive_item_id(f"{self._folder_id}").children.get()
        if items and (values := items.value):
            for item in values:
                description = item.description
                if description is None:
                    continue
                if "homeassistant_version" in description:
                    backups.append(backup_from_description(description))
        return backups

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        blob_properties = await self._items.by_drive_item_id(
            f"{self._folder_id}:/{backup_id}.tar:"
        ).get()
        if (
            blob_properties is None
            or (description := blob_properties.description) is None
        ):
            raise BackupAgentError(
                translation_domain=DOMAIN, translation_key="backup_not_found"
            )
        return backup_from_description(description)
