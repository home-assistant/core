"""Util functions for OneDrive."""

from collections.abc import AsyncIterator
from io import BytesIO
import json
import logging

from homeassistant.components.backup import AgentBackup

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
