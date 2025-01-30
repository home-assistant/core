"""Support for OneDrive backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import html
import json
import logging
from typing import Any, Concatenate, cast

from httpx import Response
from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import AnonymousAuthenticationProvider
from kiota_abstractions.headers_collection import HeadersCollection
from kiota_abstractions.method import Method
from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_abstractions.request_information import RequestInformation
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph import GraphRequestAdapter
from msgraph.generated.drives.item.items.item.content.content_request_builder import (
    ContentRequestBuilder,
)
from msgraph.generated.drives.item.items.item.create_upload_session.create_upload_session_post_request_body import (
    CreateUploadSessionPostRequestBody,
)
from msgraph.generated.drives.item.items.item.drive_item_item_request_builder import (
    DriveItemItemRequestBuilder,
)
from msgraph.generated.models.drive_item import DriveItem
from msgraph.generated.models.drive_item_uploadable_properties import (
    DriveItemUploadableProperties,
)
from msgraph_core.models import LargeFileUploadSession

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.httpx_client import get_async_client

from . import OneDriveConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
UPLOAD_CHUNK_SIZE = 16 * 320 * 1024  # 5.2MB


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[OneDriveConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
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
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


def handle_backup_errors[_R, **P](
    func: Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Handle backup errors with a specific translation key."""

    @wraps(func)
    async def wrapper(
        self: OneDriveBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except APIError as err:
            if err.response_status_code == 403:
                self._entry.async_start_reauth(self._hass)
            _LOGGER.error(
                "Error during backup in %s: Status %s, message %s",
                func.__name__,
                err.response_status_code,
                err.message,
            )
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError("Backup operation failed") from err
        except TimeoutError as err:
            _LOGGER.error(
                "Error during backup in %s: Timeout",
                func.__name__,
            )
            raise BackupAgentError("Backup operation timed out") from err

    return wrapper


class OneDriveBackupAgent(BackupAgent):
    """OneDrive backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
        """Initialize the OneDrive backup agent."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._items = entry.runtime_data.items
        self._folder_id = entry.runtime_data.backup_folder_id
        self.name = entry.title
        assert entry.unique_id
        self.unique_id = entry.unique_id

    @handle_backup_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        # this forces the query to return a raw httpx response, but breaks typing
        request_config = (
            ContentRequestBuilder.ContentRequestBuilderGetRequestConfiguration(
                options=[ResponseHandlerOption(NativeResponseHandler())],
            )
        )
        response = cast(
            Response,
            await self._get_backup_file_item(backup_id).content.get(
                request_configuration=request_config
            ),
        )

        return response.aiter_bytes(chunk_size=1024)

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
        upload_session = await self._get_backup_file_item(
            backup.backup_id
        ).create_upload_session.post(upload_session_request_body)

        if upload_session is None or upload_session.upload_url is None:
            raise BackupAgentError(
                translation_domain=DOMAIN, translation_key="backup_no_upload_session"
            )

        await self._upload_file(
            upload_session.upload_url, await open_stream(), backup.size
        )

        # store metadata in description
        backup_dict = backup.as_dict()
        backup_dict["metadata_version"] = 1  # version of the backup metadata
        description = json.dumps(backup_dict)
        _LOGGER.debug("Creating metadata: %s", description)

        await self._get_backup_file_item(backup.backup_id).patch(
            DriveItem(description=description)
        )

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""

        try:
            await self._get_backup_file_item(backup_id).delete()
        except APIError as err:
            if err.response_status_code == 404:
                return
            raise

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []
        items = await self._items.by_drive_item_id(f"{self._folder_id}").children.get()
        if items and (values := items.value):
            for item in values:
                if (description := item.description) is None:
                    continue
                if "homeassistant_version" in description:
                    backups.append(self._backup_from_description(description))
        return backups

    @handle_backup_errors
    async def async_get_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AgentBackup | None:
        """Return a backup."""
        try:
            drive_item = await self._get_backup_file_item(backup_id).get()
        except APIError as err:
            if err.response_status_code == 404:
                return None
            raise
        if (
            drive_item is not None
            and (description := drive_item.description) is not None
        ):
            return self._backup_from_description(description)
        return None

    def _backup_from_description(self, description: str) -> AgentBackup:
        """Create a backup object from a description."""
        description = html.unescape(
            description
        )  # OneDrive encodes the description on save automatically
        return AgentBackup.from_dict(json.loads(description))

    def _get_backup_file_item(self, backup_id: str) -> DriveItemItemRequestBuilder:
        return self._items.by_drive_item_id(f"{self._folder_id}:/{backup_id}.tar:")

    async def _upload_file(
        self, upload_url: str, stream: AsyncIterator[bytes], total_size: int
    ) -> None:
        """Use custom large file upload; SDK does not support stream."""

        adapter = GraphRequestAdapter(
            auth_provider=AnonymousAuthenticationProvider(),
            client=get_async_client(self._hass),
        )

        async def async_upload(
            start: int, end: int, chunk_data: bytes
        ) -> LargeFileUploadSession:
            info = RequestInformation()
            info.url = upload_url
            info.http_method = Method.PUT
            info.headers = HeadersCollection()
            info.headers.try_add("Content-Range", f"bytes {start}-{end}/{total_size}")
            info.headers.try_add("Content-Length", str(len(chunk_data)))
            info.headers.try_add("Content-Type", "application/octet-stream")
            _LOGGER.debug(info.headers.get_all())
            info.set_stream_content(chunk_data)
            result = await adapter.send_async(info, LargeFileUploadSession, {})
            _LOGGER.debug("Next expected range: %s", result.next_expected_ranges)
            return result

        start = 0
        buffer: list[bytes] = []
        buffer_size = 0

        async for chunk in stream:
            buffer.append(chunk)
            buffer_size += len(chunk)
            if buffer_size >= UPLOAD_CHUNK_SIZE:
                chunk_data = b"".join(buffer)
                uploaded_chunks = 0
                while (
                    buffer_size > UPLOAD_CHUNK_SIZE
                ):  # Loop in case the buffer is >= UPLOAD_CHUNK_SIZE * 2
                    slice_start = uploaded_chunks * UPLOAD_CHUNK_SIZE
                    await async_upload(
                        start,
                        start + UPLOAD_CHUNK_SIZE - 1,
                        chunk_data[slice_start : slice_start + UPLOAD_CHUNK_SIZE],
                    )
                    start += UPLOAD_CHUNK_SIZE
                    uploaded_chunks += 1
                    buffer_size -= UPLOAD_CHUNK_SIZE
                buffer = [chunk_data[UPLOAD_CHUNK_SIZE * uploaded_chunks :]]

        # upload the remaining bytes
        if buffer:
            _LOGGER.debug("Last chunk")
            chunk_data = b"".join(buffer)
            await async_upload(start, start + len(chunk_data) - 1, chunk_data)
