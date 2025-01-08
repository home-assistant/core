"""Util functions for OneDrive."""

from collections.abc import AsyncIterator
import html
from io import BytesIO
import json

from homeassistant.components.backup import AgentBackup


async def bytes_to_async_iterator(
    data: bytes, chunk_size: int = 1024
) -> AsyncIterator[bytes]:
    """Convert a bytes object into an AsyncIterator[bytes]."""
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


async def async_iterator_to_bytesio(async_iterator: AsyncIterator[bytes]) -> BytesIO:
    """Convert an AsyncIterator[bytes] to a BytesIO object."""
    buffer = BytesIO()
    async for chunk in async_iterator:
        buffer.write(chunk)
    buffer.seek(0)  # Reset the buffer's position to the beginning
    return buffer


def backup_from_description(description: str) -> AgentBackup:
    """Create a backup object from a description."""
    description = html.unescape(description)
    return AgentBackup.from_dict(json.loads(description))
