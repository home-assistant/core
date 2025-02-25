"""Client for SFTP Backup Location integration."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
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

from homeassistant.components.backup import BackupAgentError, suggested_filename
from homeassistant.components.backup.models import AgentBackup
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import BUF_SIZE, LOGGER
from .util import AsyncSSHFileWrapper, process_tar_from_adapter

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
        LOGGER.debug("Opening file: %s in Async File Iterator ...", file_path)

    async def _initialize(self) -> None:
        """Load file object."""
        self._client = await BackupAgentClient(self.cfg, self.hass).__aenter__()
        self._fileobj = await self._client.sftp.open(self.file_path, "rb")
        await self._fileobj.__aenter__()

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
                await self._client.__aexit__(None, None, None)
            finally:
                raise StopAsyncIteration
        return chunk


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
            LOGGER.exception(e)
            LOGGER.error(
                "Failure while attempting to establish SSH connection. Re-auth might be required."
            )
            self.cfg.async_start_reauth(self.hass)
            raise HomeAssistantError(e) from e
        await self._ssh.__aenter__()

        # Configure SFTP Client Connection
        try:
            self.sftp = await self._ssh.start_sftp_client()
            await self.sftp.__aenter__()
        except (SFTPNoSuchFile, SFTPPermissionDenied) as e:
            LOGGER.exception(e)
            LOGGER.error(
                "Failed to create SFTP client. Re-configuring integration might be required."
            )
            raise RuntimeError(
                "Failed to create SFTP client. Re-configuring integration might be required."
            ) from e

        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        """Async Context Manager exit routine."""
        if self.sftp:
            await self.sftp.__aexit__(exc_type, exc, traceback)

        if self._ssh:
            await self._ssh.__aexit__(exc_type, exc, traceback)

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

    async def async_delete_backup(self, backup: AgentBackup) -> None:
        """Delete backup archive."""

        file_path = (
            f"{self.cfg.runtime_data.backup_location}/{suggested_filename(backup)}"
        )
        assert await self.sftp.exists(file_path), (
            f"File at provided remote path: {file_path} does not exist."
        )
        assert await self.sftp.isfile(file_path), (
            f"Provided remote path: {file_path} is not file."
        )

        LOGGER.debug("Removing file at path: %s", file_path)
        await self.sftp.unlink(file_path)

    async def async_list_backups(self) -> list[AgentBackup]:
        """Iterate through backups.

        Helper method that iterates through remote files and returns
        a list of `AgentBackup` objects.
        """

        backups: list[AgentBackup] = []
        loop = asyncio.get_running_loop()

        for file in await self.list_backup_location():
            LOGGER.debug(
                "Evaluating remote file: %s@%s:%s ...",
                self.cfg.runtime_data.username,
                self.cfg.runtime_data.host,
                file,
            )
            async with self.sftp.open(file, "rb") as rfile:
                adapter = AsyncSSHFileWrapper(rfile, loop)
                try:
                    metadata = await loop.run_in_executor(
                        None, process_tar_from_adapter, adapter, file
                    )
                    if metadata is None:
                        continue
                except Exception as e:  # noqa: BLE001
                    LOGGER.exception(e)
                    LOGGER.error(
                        "Failed to load backup metadata from file: %s. Ignoring.", file
                    )
                    continue
                metadata["size"] = (await rfile.stat()).size
                backup = AgentBackup(**metadata)
                backups.append(backup)

                # Attempt to rename backup file to match the naming schema
                # of `suggested_filename` function.
                # Nothing will happen if file name is same.
                #
                # This is due to: https://github.com/home-assistant/core/issues/138853
                await self.rename(file, suggested_filename(backup))

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

    async def iter_file(self, backup: AgentBackup) -> AsyncFileIterator:
        """Return Async File Iterator object."""

        file_path = (
            f"{self.cfg.runtime_data.backup_location}/{suggested_filename(backup)}"
        )
        if not await self.sftp.isfile(file_path):
            raise BackupAgentError("Backup not found.")
        return AsyncFileIterator(self.cfg.runtime_data, file_path, BUF_SIZE)

    async def list_backup_location(self) -> list[str]:
        """Return .tar files located in backup location."""
        self._initialized()
        files = []
        LOGGER.debug(
            "Changing directory to: `%s`", self.cfg.runtime_data.backup_location
        )
        await self.sftp.chdir(self.cfg.runtime_data.backup_location)

        for file in await self.sftp.listdir():
            LOGGER.debug(
                "Checking if file: `%s` is tar file ...",
                file,
                self.cfg.runtime_data.backup_location,
            )
            if file.endswith(".tar"):
                LOGGER.debug("Found tar file name: `%s`.", file)
                files.append(f"{self.cfg.runtime_data.backup_location}/{file}")
        return files

    @asynccontextmanager
    async def open(
        self, file_path: str, mode: str = "rb"
    ) -> AsyncGenerator[SFTPClientFile]:
        """Open a remote file.

        This method opens a remote file and returns an
        :class:`SFTPClientFile` object which can be used to read and
        write data and get and set file attributes.


        The following open mode flags are supported:
          ==== =============================================
          Mode Flags
          ==== =============================================
          r    FXF_READ
          w    FXF_WRITE | FXF_CREAT | FXF_TRUNC
          a    FXF_WRITE | FXF_CREAT | FXF_APPEND
          x    FXF_WRITE | FXF_CREAT | FXF_EXCL

          r+   FXF_READ | FXF_WRITE
          w+   FXF_READ | FXF_WRITE | FXF_CREAT | FXF_TRUNC
          a+   FXF_READ | FXF_WRITE | FXF_CREAT | FXF_APPEND
          x+   FXF_READ | FXF_WRITE | FXF_CREAT | FXF_EXCL
          ==== =============================================

        Including a 'b' in the mode causes the `encoding` to be set
        to `None`, forcing all data to be read and written as bytes
        in binary format.

        :param file_path:
            The name of the remote file to open
        :param mode: (optional)
            The access mode to use for the remote file (see above)

        :returns: An :class:`SFTPClientFile` to use to access the file

        :raises: | :exc:`ValueError` if the mode is not valid
                 | :exc:`SFTPError` if the server returns an error

        """
        self._initialized(file_path=file_path)

        async with self.sftp.open(file_path, mode) as f:
            LOGGER.debug("Opening `%s` in `%s` mode.", file_path, mode)
            yield f

    async def rename(self, file_path: str, new_name: str) -> str:
        """Rename `file_path` to `new_name`.

        Returns full path to new file name.
        """
        self._initialized(file_path=file_path)

        # Change new_name to point to full backup_location path
        if not new_name.startswith(self.cfg.runtime_data.backup_location):
            new_name = f"{self.cfg.runtime_data.backup_location}/{new_name}"

        # Do nothing name is same.
        if file_path == new_name:
            return new_name

        LOGGER.debug("Renaming `%s` to `%s`.", file_path, new_name)
        await self.sftp.rename(file_path, new_name)
        return new_name
