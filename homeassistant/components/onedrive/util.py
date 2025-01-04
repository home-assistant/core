"""Util functions for OneDrive."""

from collections.abc import AsyncIterator
from io import BytesIO
import json
import logging

from kiota_abstractions.api_error import APIError
from msgraph.generated.drives.item.items.items_request_builder import (
    ItemsRequestBuilder,
)
from msgraph.generated.models.drive_item import DriveItem
from msgraph.generated.models.folder import Folder

from homeassistant.components.backup import AgentBackup
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)


async def bytes_to_async_iterator(
    data: bytes, chunk_size: int = 1024
) -> AsyncIterator[bytes]:
    """Convert a bytes object into an AsyncIterator[bytes]."""
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def parse_backup_metadata(description: str) -> AgentBackup:
    """Parse backup metadata."""
    metadata = json.loads(description)
    metadata["folders"] = json.loads(metadata.get("folders", "[]"))
    metadata["addons"] = json.loads(metadata.get("addons", "[]"))
    metadata["extra_metadata"] = json.loads(metadata.get("extra_metadata", "{}"))
    return AgentBackup.from_dict(metadata)


async def async_iterator_to_bytesio(async_iterator: AsyncIterator[bytes]) -> BytesIO:
    """Convert an AsyncIterator[bytes] to a BytesIO object."""
    buffer = BytesIO()
    async for chunk in async_iterator:
        buffer.write(chunk)
    buffer.seek(0)  # Reset the buffer's position to the beginning
    return buffer


async def async_create_folder_if_not_exists(
    items: ItemsRequestBuilder,
    folder_path: str,
) -> None:
    """Check if a folder exists and create it if it does not exist."""
    backup_folder = folder_path.strip("/")
    try:
        await items.by_drive_item_id(f"root:/{backup_folder}:").get()
    except APIError as err:
        if err.response_status_code != 404:
            raise ConfigEntryNotReady from err
        # did not exist, create it
        _LOGGER.debug("Creating backup folder %s", backup_folder)
        folders = backup_folder.split("/")
        for i, folder in enumerate(folders):
            try:
                await items.by_drive_item_id(
                    f"root:/{"/".join(folders[: i + 1])}:"
                ).get()
            except APIError as get_folder_err:
                if err.response_status_code != 404:
                    raise ConfigEntryNotReady from get_folder_err
                # is 404 not found, create folder
                _LOGGER.debug("Creating folder %s", folder)
                request_body = DriveItem(
                    name=folder,
                    folder=Folder(),
                    additional_data={
                        "@microsoft_graph_conflict_behavior": "fail",
                    },
                )
                try:
                    path = f"root:/{"/".join(folders[:i])}:" if i != 0 else "root"
                    _LOGGER.debug("Creating folder %s at %s", folder, path)
                    await items.by_drive_item_id(path).children.post(request_body)
                except APIError as create_err:
                    raise ConfigEntryError(
                        f"Failed to create folder {folder}"
                    ) from create_err
                _LOGGER.debug("Created folder %s", folder)
            else:
                _LOGGER.debug("Found folder %s", folder)
