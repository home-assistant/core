"""Client for SFTP Storage integration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
from types import TracebackType
from typing import TYPE_CHECKING, Self

from asyncssh import (
    SFTPClient,
    SFTPClientFile,
    SSHClientConnection,
    SSHClientConnectionOptions,
    connect,
)
from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgentError,
    suggested_filename,
)
from homeassistant.core import HomeAssistant

from .const import BUF_SIZE, LOGGER

if TYPE_CHECKING:
    from . import SFTPConfigEntry, SFTPConfigEntryData


def get_client_options(cfg: SFTPConfigEntryData) -> SSHClientConnectionOptions:
    """Use this function with `hass.async_add_executor_job` to asynchronously get `SSHClientConnectionOptions`."""

    return SSHClientConnectionOptions(
        known_hosts=None,
        username=cfg.username,
        password=cfg.password,
        client_keys=cfg.private_key_file,
    )


class AsyncFileIterator:
    """Returns iterator of remote file located in SFTP Server.

    This exists in order to properly close remote file after operation is completed
    and to avoid premature closing of file and session if `BackupAgentClient` is used
    as context manager.
    """

    _client: BackupAgentClient
    _fileobj: SFTPClientFile

    def __init__(
        self,
        cfg: SFTPConfigEntry,
        hass: HomeAssistant,
        file_path: str,
        buffer_size: int = BUF_SIZE,
    ) -> None:
        """Initialize `AsyncFileIterator`."""
        self.cfg: SFTPConfigEntry = cfg
        self.hass: HomeAssistant = hass
        self.file_path: str = file_path
        self.buffer_size = buffer_size
        self._initialized: bool = False
        LOGGER.debug("Opening file: %s in Async File Iterator", file_path)

    async def _initialize(self) -> None:
        """Load file object."""
        self._client: BackupAgentClient = await BackupAgentClient(
            self.cfg, self.hass
        ).open()
        self._fileobj: SFTPClientFile = await self._client.sftp.open(
            self.file_path, "rb"
        )

        self._initialized = True

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Return self as iterator."""
        return self

    async def __anext__(self) -> bytes:
        """Return next bytes as provided in buffer size."""
        if not self._initialized:
            await self._initialize()

        chunk: bytes = await self._fileobj.read(self.buffer_size)
        if not chunk:
            try:
                await self._fileobj.close()
                await self._client.close()
            finally:
                raise StopAsyncIteration
        return chunk


@dataclass(kw_only=True)
class BackupMetadata:
    """Represent single backup file metadata."""

    file_path: str
    metadata: dict[str, str | dict[str, list[str]]]
    metadata_file: str


class BackupAgentClient:
    """Helper class that manages SSH and SFTP Server connections."""

    sftp: SFTPClient

    def __init__(self, config: SFTPConfigEntry, hass: HomeAssistant) -> None:
        """Initialize `BackupAgentClient`."""
        self.cfg: SFTPConfigEntry = config
        self.hass: HomeAssistant = hass
        self._ssh: SSHClientConnection | None = None
        LOGGER.debug("Initialized with config: %s", self.cfg.runtime_data)

    async def __aenter__(self) -> Self:
        """Async context manager entrypoint."""

        return await self.open()  # type: ignore[return-value]  # mypy will otherwise raise an error

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Async Context Manager exit routine."""
        if self.sftp:
            self.sftp.exit()
            await self.sftp.wait_closed()

        if self._ssh:
            self._ssh.close()

            await self._ssh.wait_closed()

    async def _load_metadata(self, backup_id: str) -> BackupMetadata:
        """Return `BackupMetadata` object`.

        Raises:
        ------
        `FileNotFoundError` -- if metadata file is not found.

        """

        # Test for metadata file existence.
        metadata_file = (
            f"{self.cfg.runtime_data.backup_location}/.{backup_id}.metadata.json"
        )
        if not await self.sftp.exists(metadata_file):
            raise FileNotFoundError(
                f"Metadata file not found at remote location: {metadata_file}"
            )

        async with self.sftp.open(metadata_file, "r") as f:
            return BackupMetadata(
                **json.loads(await f.read()), metadata_file=metadata_file
            )

    async def async_delete_backup(self, backup_id: str) -> None:
        """Delete backup archive.

        Raises:
        ------
        `FileNotFoundError` -- if either metadata file or archive is not found.

        """

        metadata: BackupMetadata = await self._load_metadata(backup_id)

        # If for whatever reason, archive does not exist but metadata file does,
        # remove the metadata file.
        if not await self.sftp.exists(metadata.file_path):
            await self.sftp.unlink(metadata.metadata_file)
            raise FileNotFoundError(
                f"File at provided remote location: {metadata.file_path} does not exist."
            )

        LOGGER.debug("Removing file at path: %s", metadata.file_path)
        await self.sftp.unlink(metadata.file_path)
        LOGGER.debug("Removing metadata at path: %s", metadata.metadata_file)
        await self.sftp.unlink(metadata.metadata_file)

    async def async_list_backups(self) -> list[AgentBackup]:
        """Iterate through a list of metadata files and return a list of `AgentBackup` objects."""

        backups: list[AgentBackup] = []

        for file in await self.list_backup_location():
            LOGGER.debug(
                "Evaluating metadata file at remote location: %s@%s:%s",
                self.cfg.runtime_data.username,
                self.cfg.runtime_data.host,
                file,
            )

            try:
                async with self.sftp.open(file, "r") as rfile:
                    metadata = BackupMetadata(
                        **json.loads(await rfile.read()), metadata_file=file
                    )
                    backups.append(AgentBackup.from_dict(metadata.metadata))
            except (json.JSONDecodeError, TypeError) as e:
                LOGGER.error(
                    "Failed to load backup metadata from file: %s. %s", file, str(e)
                )
                continue

        return backups

    async def async_upload_backup(
        self,
        iterator: AsyncIterator[bytes],
        backup: AgentBackup,
    ) -> None:
        """Accept `iterator` as bytes iterator and write backup archive to SFTP Server."""

        file_path = (
            f"{self.cfg.runtime_data.backup_location}/{suggested_filename(backup)}"
        )
        async with self.sftp.open(file_path, "wb") as f:
            async for b in iterator:
                await f.write(b)

        LOGGER.debug("Writing backup metadata")
        metadata: dict[str, str | dict[str, list[str]]] = {
            "file_path": file_path,
            "metadata": backup.as_dict(),
        }
        async with self.sftp.open(
            f"{self.cfg.runtime_data.backup_location}/.{backup.backup_id}.metadata.json",
            "w",
        ) as f:
            await f.write(json.dumps(metadata))

    async def close(self) -> None:
        """Close the `BackupAgentClient` context manager."""
        await self.__aexit__(None, None, None)

    async def iter_file(self, backup_id: str) -> AsyncFileIterator:
        """Return Async File Iterator object.

        `SFTPClientFile` object (that would be returned with `sftp.open`) is not an iterator.
        So we return custom made class - `AsyncFileIterator` that would allow iteration on file object.

        Raises:
        ------
        - `FileNotFoundError` -- if metadata or backup archive is not found.

        """

        metadata: BackupMetadata = await self._load_metadata(backup_id)
        if not await self.sftp.exists(metadata.file_path):
            raise FileNotFoundError("Backup archive not found on remote location.")
        return AsyncFileIterator(self.cfg, self.hass, metadata.file_path, BUF_SIZE)

    async def list_backup_location(self) -> list[str]:
        """Return a list of `*.metadata.json` files located in backup location."""
        files = []
        LOGGER.debug(
            "Changing directory to: `%s`", self.cfg.runtime_data.backup_location
        )
        await self.sftp.chdir(self.cfg.runtime_data.backup_location)

        for file in await self.sftp.listdir():
            LOGGER.debug(
                "Checking if file: `%s/%s` is metadata file",
                self.cfg.runtime_data.backup_location,
                file,
            )
            if file.endswith(".metadata.json"):
                LOGGER.debug("Found metadata file: `%s`", file)
                files.append(f"{self.cfg.runtime_data.backup_location}/{file}")
        return files

    async def open(self) -> BackupAgentClient:
        """Return initialized `BackupAgentClient`.

        This is to avoid calling `__aenter__` dunder method.
        """

        # Configure SSH Client Connection
        try:
            self._ssh = await connect(
                host=self.cfg.runtime_data.host,
                port=self.cfg.runtime_data.port,
                options=await self.hass.async_add_executor_job(
                    get_client_options, self.cfg.runtime_data
                ),
            )
        except (OSError, PermissionDenied) as e:
            raise BackupAgentError(
                "Failure while attempting to establish SSH connection. Please check SSH credentials and if changed, re-install the integration"
            ) from e

        # Configure SFTP Client Connection
        try:
            self.sftp = await self._ssh.start_sftp_client()
            await self.sftp.chdir(self.cfg.runtime_data.backup_location)
        except (SFTPNoSuchFile, SFTPPermissionDenied) as e:
            raise BackupAgentError(
                "Failed to create SFTP client. Re-installing integration might be required"
            ) from e

        return self
