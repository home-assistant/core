"""Util functions for OneDrive."""

from collections.abc import AsyncIterator
import json
from typing import Any

from homeassistant.components.backup import AgentBackup


async def bytes_to_async_iterator(
    data: bytes, chunk_size: int = 1024
) -> AsyncIterator[bytes]:
    """Convert a bytes object into an AsyncIterator[bytes]."""
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def parse_backup_metadata(metadata: dict[str, Any]) -> AgentBackup:
    """Parse backup metadata."""
    metadata["folders"] = json.loads(metadata.get("folders", "[]"))
    metadata["addons"] = json.loads(metadata.get("addons", "[]"))
    metadata["extra_metadata"] = json.loads(metadata.get("extra_metadata", "{}"))
    return AgentBackup.from_dict(metadata)
