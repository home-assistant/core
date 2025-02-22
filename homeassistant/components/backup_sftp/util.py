"""Utilities for the SFTP Backup Location integration."""

import asyncio
import io
import json
import tarfile
from typing import cast

from asyncssh.sftp import SFTPClientFile

from homeassistant.components.backup.models import AddonInfo, Folder


class AsyncSSHFileWrapper(io.RawIOBase):
    """A synchronous file-like adapter that wraps an asyncssh SFTP file.

    Used when non-async functions need to access file-like object.
    """

    def __init__(self, async_file: SFTPClientFile, loop: asyncio.AbstractEventLoop):
        """Initialize `AsyncSSHFileWrapper`."""
        self.async_file = async_file
        self.loop = loop

    def read(self, size=-1) -> bytes:
        """Read file, returns bytes."""
        future = asyncio.run_coroutine_threadsafe(self.async_file.read(size), self.loop)
        return future.result()

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Seeks through file."""
        future = asyncio.run_coroutine_threadsafe(
            self.async_file.seek(offset, whence), self.loop
        )
        return future.result()

    def tell(self) -> int:
        """Report current position in file."""
        future = asyncio.run_coroutine_threadsafe(self.async_file.tell(), self.loop)
        return future.result()


def get_backup_metadata(cfg: dict) -> dict:
    """Return dict ready for AgentBackup model from backup.json metadata.

    `size` attribute is missing and is to be specified by main call.
    """

    assert isinstance(cfg, dict) and "homeassistant" in cfg, (
        "Provided object is not dict or not a valid backup metadata."
    )

    if cfg["homeassistant"]:
        database_included = not cfg["homeassistant"]["exclude_database"]
        homeassistant_included = True
        homeassistant_version = cfg["homeassistant"]["version"]
    else:
        database_included = False
        homeassistant_included = False
        homeassistant_version = None

    return {
        "backup_id": cfg["slug"],
        "database_included": database_included,
        "date": cfg["date"],
        "extra_metadata": cfg["extra"],
        "homeassistant_included": homeassistant_included,
        "homeassistant_version": homeassistant_version,
        "name": cfg["name"],
        "protected": cfg["protected"],
        "addons": [
            AddonInfo(name=addon["name"], slug=addon["slug"], version=addon["version"])
            for addon in cfg["addons"]
        ],
        "folders": [Folder(f) for f in cfg["folders"]],
    }


def process_tar_from_adapter(adapter: AsyncSSHFileWrapper, file: str) -> dict:
    """Open ./backup.json from backup file archive.

    KeyError is raised if file does not exist in archive (not a valid backup)
    and same exception is raised if any values from config files are missing
    ...again, indicating that the mentioned .tar file may not be home assistant backup.
    """
    with tarfile.open(mode="r", fileobj=adapter) as t:
        # Force the IDE to treat 't' as a TarFile:
        tar = cast(tarfile.TarFile, t)

        try:
            fileobj = tar.getmember("./backup.json")
        except KeyError:
            return None

        try:
            cfg = json.load(tar.extractfile(fileobj))
        except Exception as e:
            raise AssertionError(f"Provided file ({file}) cannot be loaded as json.") from e
    return get_backup_metadata(cfg)
