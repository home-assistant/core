"""Mock classes for asyncssh module."""

from __future__ import annotations

import json
from typing import Self
from unittest.mock import AsyncMock

from asyncssh.misc import async_context_manager


class SSHClientConnectionMock:
    """Class that mocks SSH Client connection."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize SSHClientConnectionMock."""
        self._sftp: SFTPClientMock = SFTPClientMock()

    async def __aenter__(self) -> Self:
        """Allow SSHClientConnectionMock to be used as an async context manager."""
        return self

    async def __aexit__(self, *args) -> None:
        """Allow SSHClientConnectionMock to be used as an async context manager."""
        self.close()

    def close(self):
        """Mock `close` from `SSHClientConnection`."""
        return

    def mock_setup_backup(self, metadata: dict, with_bad: bool = False) -> str:
        """Setup mocks to properly return a backup.

        Return: Backup ID (slug)
        """

        slug = metadata["metadata"]["backup_id"]
        side_effect = [
            json.dumps(metadata),  # from async_list_backups
            json.dumps(metadata),  # from iter_file -> _load_metadata
            b"backup data",  # from AsyncFileIterator
            b"",
        ]
        self._sftp._mock_listdir.return_value = [f"{slug}.metadata.json"]

        if with_bad:
            side_effect.insert(0, "invalid")
            self._sftp._mock_listdir.return_value = [
                "invalid.metadata.json",
                f"{slug}.metadata.json",
            ]

        self._sftp._mock_open._mock_read.side_effect = side_effect
        return slug

    @async_context_manager
    async def start_sftp_client(self, *args, **kwargs) -> SFTPClientMock:
        """Return mocked SFTP Client."""
        return self._sftp

    async def wait_closed(self):
        """Mock `wait_closed` from `SFTPClient`."""
        return


class SFTPClientMock:
    """Class that mocks SFTP Client connection."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize `SFTPClientMock`."""
        self._mock_chdir = AsyncMock()
        self._mock_listdir = AsyncMock()
        self._mock_exists = AsyncMock(return_value=True)
        self._mock_unlink = AsyncMock()
        self._mock_open = SFTPOpenMock()

    async def __aenter__(self) -> Self:
        """Allow SFTPClientMock to be used as an async context manager."""
        return self

    async def __aexit__(self, *args) -> None:
        """Allow SFTPClientMock to be used as an async context manager."""
        self.exit()

    async def chdir(self, *args) -> None:
        """Mock `chdir` method from SFTPClient."""
        await self._mock_chdir(*args)

    async def listdir(self, *args) -> list[str]:
        """Mock `listdir` method from SFTPClient."""
        result = await self._mock_listdir(*args)
        return result if result is not None else []

    @async_context_manager
    async def open(self, *args, **kwargs) -> SFTPOpenMock:
        """Mock open a remote file."""
        return self._mock_open

    async def exists(self, *args) -> bool:
        """Mock `exists` method from SFTPClient."""
        return await self._mock_exists(*args)

    async def unlink(self, *args) -> None:
        """Mock `unlink` method from SFTPClient."""
        await self._mock_unlink(*args)

    def exit(self):
        """Mandatory method for quitting SFTP Client."""
        return

    async def wait_closed(self):
        """Mock `wait_closed` from `SFTPClient`."""
        return


class SFTPOpenMock:
    """Mocked remote file."""

    def __init__(self) -> None:
        """Initialize arguments for mocked responses."""
        self._mock_read = AsyncMock(return_value=b"")
        self._mock_write = AsyncMock()
        self.close = AsyncMock(return_value=None)

    async def __aenter__(self):
        """Allow SFTPOpenMock to be used as an async context manager."""
        return self

    async def __aexit__(self, *args) -> None:
        """Allow SFTPOpenMock to be used as an async context manager."""

    async def read(self, *args, **kwargs) -> bytes:
        """Read remote file - mocked response from `self._mock_read`."""
        return await self._mock_read(*args, **kwargs)

    async def write(self, content, *args, **kwargs) -> int:
        """Mock write to remote file."""
        await self._mock_write(content, *args, **kwargs)
        return len(content)
