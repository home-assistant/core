"""Client for SFTP Backup Location integration."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from asyncssh import (
    SFTPClient,
    SFTPClientFile,
    SSHClientConnection,
    SSHClientConnectionOptions,
    connect,
)
from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied

from homeassistant.components.backup import AgentBackup, suggested_filename
from homeassistant.core import HomeAssistant

from .const import BUF_SIZE, LOGGER

if TYPE_CHECKING:
    from . import SFTPConfigEntry


class AsyncFileIterator:
    """Returns iterator of remote file located in SFTP Server.

    This exists in order to properly close remote file after operation is completed
    and to avoid premature closing of file and session if `BackupAgentClient` is used
    as context manager.
    """

    def __init__(
        self,
        cfg: "SFTPConfigEntry",
        hass: HomeAssistant,
        file_path: str,
        buffer_size: int = BUF_SIZE,
    ) -> None:
        """Initialize `AsyncFileIterator`."""
        self.cfg: SFTPConfigEntry = cfg
        self.hass: HomeAssistant = hass
        self.file_path: str = file_path
        self.buffer_size = buffer_size
        self._client: BackupAgentClient | None = None
        self._fileobj: SFTPClientFile | None = None
        self._initialized: bool = False
        LOGGER.debug("Opening file: %s in Async File Iterator", file_path)

    async def _initialize(self) -> None:
        """Load file object."""
        self._client = await BackupAgentClient(self.cfg, self.hass).open()  # pylint: disable=unnecessary-dunder-call
        self._fileobj = await self._client.sftp.open(self.file_path, "rb")
        await self._fileobj.__aenter__()  # pylint: disable=unnecessary-dunder-call

        self._initialized = True

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Return self as iterator."""
        return self

    async def __anext__(self) -> bytes:
        """Return next bytes as provided in buffer size."""
        if not self._initialized:
            await self._initialize()

        chunk = await self._fileobj.read(self.buffer_size)
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
    metadata: dict[str, str | dict[str | list[str]]]
    metadata_file: str


class BackupAgentError(Exception):
    """Base exception for `BackupAgentClient` class."""


class BackupAgentAuthError(BackupAgentError):
    """Exception raised when authentication fails after being initially setup."""


class BackupAgentClient:
    """Helper class that manages SSH and SFTP Server connections."""

    def __init__(self, config: "SFTPConfigEntry", hass: HomeAssistant) -> None:
        """Initialize `BackupAgentClient`."""
        self.cfg: SFTPConfigEntry = config
        self.hass: HomeAssistant = hass
        self._ssh: SSHClientConnection | None = None
        self.sftp: SFTPClient | None = None
        LOGGER.debug("Initialized with config: %s", self.cfg.runtime_data)

    async def __aenter__(self) -> "BackupAgentClient":
        """Async context manager entrypoint."""

        # Configure SSH Client Connection
        try:
            self._ssh = await connect(
                host=self.cfg.runtime_data.host,
                port=self.cfg.runtime_data.port,
                options=SSHClientConnectionOptions(
                    known_hosts=None,
                    username=self.cfg.runtime_data.username,
                    password=self.cfg.runtime_data.password,
                    client_keys=[self.cfg.runtime_data.private_key_file]
                    if self.cfg.runtime_data.private_key_file
                    else None,
                ),
            )
        except (OSError, PermissionDenied) as e:
            LOGGER.error(
                "Failure while attempting to establish SSH connection. Re-auth might be required."
                " Please check SSH credentials and if changed, re-add the integration"
            )
            raise BackupAgentAuthError(
                "Failure while attempting to establish SSH connection. Re-auth might be required."
            ) from e

        # We are manually calling `__aenter__` on `self._ssh` and `self.sftp` because both
        # are async context managers that require initialization. This ensures they're properly
        # set up and managed within the BackupAgentClient context,
        # allowing a single `async with BackupAgentClient` to handle both.
        await self._ssh.__aenter__()

        # Configure SFTP Client Connection
        try:
            self.sftp = await self._ssh.start_sftp_client()
            await self.sftp.__aenter__()
        except (SFTPNoSuchFile, SFTPPermissionDenied) as e:
            LOGGER.exception(e)
            LOGGER.error(
                "Failed to create SFTP client. Re-configuring integration might be required"
            )
            raise RuntimeError(
                "Failed to create SFTP client. Re-configuring integration might be required"
            ) from e

        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        """Async Context Manager exit routine."""
        if self.sftp:
            self.sftp.exit()
            await self.sftp.wait_closed()

        if self._ssh:
            self._ssh.close()

            await self._ssh.wait_closed()

    def _initialized(self, file_path: str | None = None) -> None:
        """Check if SSH Connection is initialized.

        If `file_path` is provided, also checks if
        it's not within scope of configured backup location.

        Raises `RuntimeError` if either checks fail.
        """
        if self._ssh is None or self.sftp is None:
            raise RuntimeError("Connection is not initialized.")

        if file_path and not file_path.startswith(
            self.cfg.runtime_data.backup_location
        ):
            raise RuntimeError(
                f"Attempted to access file outside of configured backup location: {file_path}"
            )

    async def _load_metadata(self, backup: AgentBackup) -> BackupMetadata:
        """Return `BackupMetadata` object`.

        Raises
        ------
        `AssertionError` -- if metadata file is not found.

        """

        metadata_file = f"{self.cfg.runtime_data.backup_location}/.{backup.backup_id}.metadata.json"
        if not await self.sftp.exists(metadata_file):
            raise FileNotFoundError(f"Metadata file not found at remote location: {metadata_file}")

        async with self.sftp.open(metadata_file, "r") as f:
            return BackupMetadata(
                **json.loads(await f.read()), metadata_file=metadata_file
            )

    async def async_delete_backup(self, backup: AgentBackup) -> None:
        """Delete backup archive.

        Raises
        ------
        `AssertionError` -- if either metadata file or archive is not found.

        """

        metadata: BackupMetadata = await self._load_metadata(backup)

        # If for whatever reason, archive does not exist but metadata file does,
        # remove the metadata file.
        if not await self.sftp.exists(metadata.file_path):
            await self.sftp.unlink(metadata.metadata_file)
            raise FileNotFoundError(f"File at provided remote location: {metadata.file_path} does not exist.")

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
            except Exception as e:  # noqa: BLE001
                LOGGER.exception(e)
                LOGGER.error(
                    "Failed to load backup metadata from file: %s. Ignoring", file
                )
                continue

        return backups

    async def async_upload_backup(
        self,
        iterator: AsyncIterator[bytes],
        backup: AgentBackup,
    ) -> list[AgentBackup]:
        """Accept `iterator` as bytes iterator and write backup archive to SFTP Server."""

        file_path = (
            f"{self.cfg.runtime_data.backup_location}/{suggested_filename(backup)}"
        )
        async with self.sftp.open(file_path, "wb") as f:
            async for b in iterator:
                await f.write(b)

        LOGGER.debug("Writing backup metadata")
        metadata: dict[str, str] = {
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

    async def iter_file(self, backup: AgentBackup) -> AsyncFileIterator:
        """Return Async File Iterator object.

        `SFTPClientFile` object (that would be returned with `sftp.open`) is not an iterator.
        So we return custom made class - `AsyncFileIterator` that would allow iteration on file object.

        Raises
        ------
        - `AssertionError` -- if metadata file is not found.
        - `FileNotFoundError` -- if backup archive is not found.

        """

        metadata: BackupMetadata = await self._load_metadata(backup)
        if not await self.sftp.exists(metadata.file_path):
            raise FileNotFoundError("Backup archive not found on remote location.")
        return AsyncFileIterator(self.cfg, self.hass, metadata.file_path, BUF_SIZE)

    async def list_backup_location(self) -> list[str]:
        """Return a list of `*.metadata.json` files located in backup location."""
        self._initialized()
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

    async def open(self) -> "BackupAgentClient":
        """Return initialized `BackupAgentClient`.

        This is to avoid calling `__aenter__` dunder method.
        """
        return await self.__aenter__()
