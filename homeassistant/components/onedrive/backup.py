"""Support for OneDrive backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import json
import logging
from typing import Any, Concatenate, cast

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import AnonymousAuthenticationProvider
from kiota_abstractions.method import Method
from kiota_abstractions.request_information import RequestInformation
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
from .util import async_iterator_to_bytesio, backup_from_description

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


def handle_backup_errors[_R, **P](
    translation_key: str,
) -> Callable[
    [Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]]],
    Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]],
]:
    """Handle backup errors with a specific translation key."""

    def decorator(
        func: Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]],
    ) -> Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]]:
        @wraps(func)
        async def wrapper(
            self: OneDriveBackupAgent, *args: P.args, **kwargs: P.kwargs
        ) -> _R:
            try:
                return await func(self, *args, **kwargs)
            except APIError as err:
                _LOGGER.error(
                    "Error during backup in %s: Status %s, message %s",
                    func.__name__,
                    err.response_status_code,
                    err.message,
                )
                _LOGGER.debug("Full error: %s", err, exc_info=True)
                raise BackupAgentError(
                    translation_domain=DOMAIN, translation_key=translation_key
                ) from err

        return wrapper

    return decorator


class OneDriveBackupAgent(BackupAgent):
    """OneDrive backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
        """Initialize the OneDrive backup agent."""
        super().__init__()
        self._client = entry.runtime_data.client
        assert entry.unique_id
        self._items = self._client.drives.by_drive_id(entry.unique_id).items
        self._folder_id = entry.runtime_data.backup_folder_id
        self._anonymous_auth_adapter = GraphRequestAdapter(
            auth_provider=AnonymousAuthenticationProvider(),
            client=get_async_client(hass),
        )
        self.name = entry.title

    @handle_backup_errors("failed_to_download_backup")
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        content = self._items.by_drive_item_id(
            f"{self._folder_id}:/{backup_id}.tar:"
        ).content
        # since the SDK only supports downloading the full file, we need to use the raw request adapter
        request_info = RequestInformation(
            method=Method.GET,
            url_template=content.url_template,
            path_parameters=content.path_parameters,
        )
        request_adapter = cast(GraphRequestAdapter, self._client.request_adapter)
        parent_span = request_adapter.start_tracing_span(
            request_info, "download_backup"
        )
        response = await request_adapter.get_http_response_message(
            request_info=request_info, parent_span=parent_span
        )
        return response.aiter_bytes(chunk_size=1024)  # type: ignore[no-any-return]

    @handle_backup_errors("failed_to_create_backup")
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

    @handle_backup_errors("failed_to_delete_backup")
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        await self._items.by_drive_item_id(
            f"{self._folder_id}:/{backup_id}.tar:"
        ).delete()

    @handle_backup_errors("failed_to_list_backups")
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []
        items = await self._items.by_drive_item_id(f"{self._folder_id}").children.get()
        if items and (values := items.value):
            for item in values:
                if (description := item.description) is None:
                    continue
                if "homeassistant_version" in description:
                    backups.append(backup_from_description(description))
        return backups

    @handle_backup_errors("failed_to_get_backup")
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
