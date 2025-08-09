"""Helper functions for the SFTPClient component."""

from __future__ import annotations

from collections.abc import AsyncIterator
import logging

from asyncssh import (
    Error,
    PermissionDenied,
    SFTPClient,
    SFTPError,
    SSHClientConnection,
    connect,
)

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class SSHClient:
    """SSH Client."""

    def __init__(
        self, *, host: str, username: str, password: str, ssl: bool = False
    ) -> None:
        """Initialize."""
        self.host = host
        self._username = username
        self._password = password
        self._ssl = ssl
        self._conn: SSHClientConnection | None = None

    async def async_ssh_connect(self) -> None:
        """Create a ssh connection."""
        try:
            self._conn = await connect(
                self.host,
                username=self._username,
                password=self._password,
                known_hosts=None,
            )
        except PermissionDenied as error:
            raise InvalidAuth(error) from error
        except (Error, OSError) as error:
            raise CannotConnect(error) from error

    async def async_ssh_close(self) -> None:
        """Close SSH session."""
        if self._conn is not None:
            try:
                self._conn.close()
                await self._conn.wait_closed()
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Error while closing SSH connection: %s", e)
            finally:
                self._conn = None


class SFTPConnection(SSHClient):
    """Client."""

    client: SFTPClient | None = None

    async def async_connect(self) -> None:
        """Open SFTP Connection."""
        await self.async_ssh_connect()
        if self._conn is None:
            raise RuntimeError("SSH connection failed")

        try:
            self.client = await self._conn.start_sftp_client()
        except (ConnectionRefusedError, SFTPError) as error:
            raise CannotConnect(error) from error

    async def async_close(self) -> None:
        """Close SFTP Connection."""
        if self.client:
            try:
                self.client.exit()
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Error while closing SFTP client: %s", e)
            self.client = None
        await self.async_ssh_close()

    async def async_ensure_path_exists(self, path: str) -> bool:
        """Ensure that a path exists recursively on the SFTP server."""
        if self.client is None:
            raise RuntimeError("SFTP client not connected")
        return await self.client.isdir(path)

    async def async_create_backup_path(self, path: str) -> None:
        """Create backup folder."""
        if self.client is None:
            raise RuntimeError("SFTP client not connected")
        try:
            if not await self.client.isdir(path):
                await self.client.mkdir(path)
        except SFTPError as error:
            raise BackupFolderError("Failed to create a backup folder") from error

    async def async_read(self, path: str) -> str:
        """Read a file from the SFTP server."""
        if self.client is None:
            raise RuntimeError("SFTP Error")
        async with self.client.open(path, "rb") as sftp_file:
            chunks: list[bytes] = []
            while True:
                chunk: bytes = await sftp_file.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        metadata_bytes = b"".join(chunks)
        return metadata_bytes.decode("utf-8")


def json_to_stream(json_str: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
    """Convert a JSON string into an async iterator of bytes."""

    async def generator() -> AsyncIterator[bytes]:
        encoded = json_str.encode("utf-8")
        for i in range(0, len(encoded), chunk_size):
            yield encoded[i : i + chunk_size]

    return generator()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class BackupFolderError(HomeAssistantError):
    """Error indicating that the directory being backed up is incorrect."""
