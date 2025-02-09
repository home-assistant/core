"""Backup platform for the SFTP Backup Storage integration."""

from __future__ import annotations

import asyncio
import json
import re
import tarfile

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any, Self

from homeassistant.components.backup import (
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    Folder,
)
from homeassistant.core import HomeAssistant, callback

from . import SFTPConfigEntry
from .client import SSHClient
from .const import (
    CONF_BACKUP_LOCATION,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    LOGGER,
)
from .util import BufferedAsyncIteratorToSyncStream


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Register the backup agents."""
    entries: list[SFTPConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    return [SFTPBackupAgent(hass, entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed."""
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)

    return remove_listener


class SFTPAsyncStreamIterator:
    """Async iterator for streaming SFTP file content.

    This creates new SSHClient because using the original one will block
    the Home Assistant if backups are opened in another tab while current
    backup is being downloaded.
    """

    __slots__ = ("_client", "_sftp_file", "_chunk_size")

    def __init__(
        self, runtime_data: SFTPConfigEntry, file: str, chunk_size: int = 8192
    ) -> None:
        """Initialize the async iterator.

        Args:
            sftp_file (SFTPFile): Paramiko SFTP file object.
            chunk_size (int): Size of each chunk to read. Defaults to 8192 bytes.
        """
        client = SSHClient(
            host=runtime_data.host,
            port=runtime_data.port,
            username=runtime_data.username,
            password=runtime_data.password,
            private_key_file=runtime_data.private_key_file,
        )

        self._client = client
        self._sftp_file = client.sftp.open(file, "rb")
        self._chunk_size = chunk_size

    def __aiter__(self) -> Self:
        """Return the async iterator instance."""
        return self

    async def __anext__(self) -> bytes:
        """Yield the next chunk of data or stop iteration."""
        # Read a chunk of data asynchronously using asyncio.to_thread
        chunk = await asyncio.to_thread(self._sftp_file.read, self._chunk_size)

        if not chunk:  # Empty chunk indicates end of file
            self._sftp_file.close()
            self._client.close()
            raise StopAsyncIteration
        return chunk


class SFTPBackupAgent(BackupAgent):
    """SFTP Backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: SFTPConfigEntry) -> None:
        """Initialize the SFTPBackupAgent backup sync agent."""
        super().__init__()
        self._entry = entry
        self._host = (
            f"{self._entry.runtime_data.username}@{self._entry.runtime_data.host}"
        )
        self._hass = hass
        self.name = entry.title
        self.domain = DOMAIN

    @property
    def unique_id(self) -> str:
        """
        Returns unique identifier that consists of:
        `backup_sftp.<host>.<port>.<username>.<remote_path>`.
        `remote_path` has all non-alphanumeric characters replaced by `_`, as well as `host`
        and `username`.
        """
        host = re.sub(r"[^a-zA-Z\d\s:]", "_", self._entry.runtime_data.host)
        remote_path = re.sub(
            r"[^a-zA-Z\d\s:]", "_", self._entry.runtime_data.backup_location
        )
        user = re.sub(r"[^a-zA-Z\d\s:]", "_", self._entry.runtime_data.username)

        return (
            f"backup_sftp.{host}.{self._entry.runtime_data.port}.{user}.{remote_path}"
        )

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file from SFTP."""
        if not await self.async_get_backup(backup_id):
            raise BackupAgentError("Backup not found")

        file = f"{self._entry.data[CONF_BACKUP_LOCATION]}/{backup_id}.tar"
        LOGGER.debug("Downloading file: %s", file)

        return SFTPAsyncStreamIterator(runtime_data=self._entry.runtime_data, file=file)

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        def upload(
            ssh: SSHClient, stream: BufferedAsyncIteratorToSyncStream = None
        ) -> None:
            _in, out, err = ssh.exec_command(f"cat - > {file_path}")
            try:
                while b := stream.read(8 * 1024 * 1024):
                    _in.write(b)
            except Exception as e:
                raise BackupAgentError(
                    f"Failed to upload backup to {self._host}:{file_path} due to exception ({type(e).__name__}). {e}"
                ) from e
            else:
                LOGGER.debug(
                    f"Backup file successfully uploaded to {self._host}:{file_path}."
                )
            finally:
                _in.close()

            ec = out.channel.recv_exit_status()
            if ec > 0:
                LOGGER.error(
                    f"Failed to upload backup to {file_path}. Received exit code: {ec}. STDERR: {err.read().decode().strip()}"
                )
                raise BackupAgentError(
                    f"Failed to upload backup to {self._host}:{file_path}. Received exit code: {ec}"
                )

        """Upload a backup."""
        # Upload the file with metadata
        file_path = f"{self._entry.data[CONF_BACKUP_LOCATION]}/{backup.backup_id}.tar"

        iterator = await open_stream()
        stream = BufferedAsyncIteratorToSyncStream(
            iterator,
            buffer_size=8 * 1024 * 1024,  # Buffer up to 8MB
        )

        # This is dirty. But should work if we don't run into https://github.com/paramiko/paramiko/issues/822
        # Alternative would be to write to NamedTemporaryFile and then copy the file via sftp. But then we would
        # (temporarily) increase disk usage on Home Assistant host.
        with self._entry.runtime_data.client() as ssh:
            await self._hass.async_add_executor_job(upload, ssh, stream)

    def _delete_backup(
        self,
        ssh: SSHClient,
        backup_id: str,
    ) -> None:
        """Delete file from SFTP Backup Storage."""

        sftp = ssh.open_sftp()
        backup_file = f"{self._entry.data[CONF_BACKUP_LOCATION]}/{backup_id}.tar"

        try:
            sftp.remove(backup_file)
        except Exception as err:  # noqa: BLE001
            LOGGER.error("Can not delete backups from location: %s", err)
            raise BackupAgentError(f"Failed to delete backups: {err}") from err
        else:
            LOGGER.debug(
                f"Successfully removed backup file at location: {self._host}:{backup_file}"
            )

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file from SFTP Backup Storage."""
        if not await self.async_get_backup(backup_id):
            return

        with self._entry.runtime_data.client() as ssh:
            await self._hass.async_add_executor_job(self._delete_backup, ssh, backup_id)

    def _get_backup_info(self, tar: tarfile.TarFile, fileobj: tarfile.TarInfo) -> dict:
        cfg = json.load(tar.extractfile(fileobj))
        LOGGER.debug(
            f"Original contents of backup.json for file {fileobj.tarfile.name}: {cfg}"
        )

        if cfg["homeassistant"]:
            database_included = not cfg["homeassistant"]["exclude_database"]
            homeassistant_included = True
            homeassistant_version = cfg["homeassistant"]["version"]
        else:
            database_included = False
            homeassistant_included = False
            homeassistant_version = None

        stub = {
            "backup_id": cfg["slug"],
            "database_included": database_included,
            "date": cfg["date"],
            "extra_metadata": cfg["extra"],
            "homeassistant_included": homeassistant_included,
            "homeassistant_version": homeassistant_version,
            "name": cfg["name"],
            "protected": cfg["protected"],
            "addons": cfg["addons"],
            "folders": cfg["folders"],
        }

        return stub

    def _list_backups(self, ssh: SSHClient) -> list[AgentBackup]:
        backups = []
        sftp = ssh.open_sftp()
        sftp.chdir(self._entry.data[CONF_BACKUP_LOCATION])

        for file in sftp.listdir():
            # Evaluate every file in remote directory that ends with .tar
            if file.endswith(".tar"):
                LOGGER.debug(
                    f"Evaluating remote file: {self._host}:{self._entry.data[CONF_BACKUP_LOCATION]}/{file} ..."
                )

                # Opens ./backup.json from backup file, KeyError is raised if
                # file does not exist in archive (not a valid backup)
                # and same exception is raised if any values from config files are missing
                # ...again, indicating that the mentioned .tar file may not be home assistant backup.
                with tarfile.open(mode="r", fileobj=sftp.open(file)) as tar:
                    try:
                        fileobj = tar.getmember("./backup.json")
                    except KeyError:
                        continue
                    else:
                        setattr(
                            tar,
                            "name",
                            f"{self._entry.data[CONF_BACKUP_LOCATION]}/{file}",
                        )
                        fileobj.tarfile = tar
                        file_info = self._get_backup_info(tar, fileobj)

                    LOGGER.debug(
                        f"Obtained remote file info for file {self._host}:{file}: {file_info}"
                    )

                backup_id = file_info["backup_id"]

                # Extract size
                file_info["size"] = sftp.stat(file).st_size

                # Extract addons
                # Turns original addons list into a list of AddonInfo as expected by AgentBackup
                file_info["addons"] = [
                    AddonInfo(
                        name=addon["name"], slug=addon["slug"], version=addon["version"]
                    )
                    for addon in file_info["addons"]
                ]

                # Extract folders
                # Turns original folders list into a list of Folder as expected by AgentBackup
                file_info["folders"] = [Folder(f) for f in file_info["folders"]]

                backups.append(
                    AgentBackup(
                        backup_id=backup_id,
                        name=file_info["name"],
                        date=file_info["date"],
                        size=file_info["size"],
                        homeassistant_version=file_info["homeassistant_version"],
                        protected=file_info["protected"],
                        addons=file_info["addons"],
                        folders=file_info["folders"],
                        database_included=file_info["database_included"],
                        homeassistant_included=file_info["database_included"],
                        extra_metadata=file_info["extra_metadata"],
                    )
                )
                LOGGER.debug(f"Added backup: {backups[-1]} from file: {file}.")

        return backups

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups stored on SFTP Backup Storage."""
        with self._entry.runtime_data.client() as ssh:
            return await self._hass.async_add_executor_job(self._list_backups, ssh)

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        backups = await self.async_list_backups()

        for backup in backups:
            if backup.backup_id == backup_id:
                LOGGER.debug(f"Returning backup id: {backup_id}. {backup}")
                return backup

        return None
