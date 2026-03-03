"""API for Dropbox bound to Home Assistant OAuth."""

from collections.abc import AsyncIterator, Callable, Coroutine
import json
import logging
from typing import Any

from python_dropbox_api import (
    AccountInfo,
    Auth,
    DropboxAPIClient,
    DropboxAuthException,
    DropboxUnknownException,
)

from homeassistant.components.backup import (
    AgentBackup,
    BackupNotFound,
    suggested_filename,
)

_LOGGER = logging.getLogger(__name__)


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


async def _async_string_iterator(content: str) -> AsyncIterator[bytes]:
    """Yield a string as a single bytes chunk."""
    yield content.encode()


class DropboxClient:
    """Dropbox client."""

    def __init__(self, auth: Auth) -> None:
        """Initialize Dropbox client."""
        self._api = DropboxAPIClient(auth)

    async def async_get_account_info(self) -> AccountInfo:
        """Get information about the current account."""
        return await self._api.get_account_info()

    async def _async_get_backups(self) -> list[tuple[AgentBackup, str]]:
        """Get backups and their corresponding file names."""
        files = await self._api.list_folder("")

        tar_files = {f.name for f in files if f.name.endswith(".tar")}
        metadata_files = [f for f in files if f.name.endswith(".metadata.json")]

        backups: list[tuple[AgentBackup, str]] = []
        for metadata_file in metadata_files:
            tar_name = metadata_file.name.removesuffix(".metadata.json") + ".tar"
            if tar_name not in tar_files:
                _LOGGER.warning(
                    "Found metadata file '%s' without matching backup file",
                    metadata_file.name,
                )
                continue

            metadata_stream = self._api.download_file(f"/{metadata_file.name}")
            raw = b"".join([chunk async for chunk in metadata_stream])
            backup = AgentBackup.from_dict(json.loads(raw))
            backups.append((backup, tar_name))

        return backups

    async def async_list_backups(self) -> list[AgentBackup]:
        """List backups."""
        return [backup for backup, _ in await self._async_get_backups()]

    async def async_upload_backup(
        self,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        """Upload a backup."""
        backup_filename, metadata_filename = suggested_filenames(backup)
        backup_path = f"/{backup_filename}"
        metadata_path = f"/{metadata_filename}"

        file_stream = await open_stream()
        await self._api.upload_file(backup_path, file_stream)

        metadata_stream = _async_string_iterator(json.dumps(backup.as_dict()))

        try:
            await self._api.upload_file(metadata_path, metadata_stream)
        except (
            DropboxAuthException,
            DropboxUnknownException,
        ):
            await self._api.delete_file(backup_path)
            raise

    async def async_download_backup(self, backup_id: str) -> AsyncIterator[bytes]:
        """Download a backup."""
        backups = await self._async_get_backups()
        for backup, filename in backups:
            if backup.backup_id == backup_id:
                return self._api.download_file(f"/{filename}")

        raise BackupNotFound(f"Backup {backup_id} not found")

    async def async_delete_backup(self, backup_id: str) -> None:
        """Delete a backup."""
        backups = await self._async_get_backups()
        for backup, tar_filename in backups:
            if backup.backup_id == backup_id:
                metadata_filename = tar_filename.removesuffix(".tar") + ".metadata.json"
                await self._api.delete_file(f"/{tar_filename}")
                await self._api.delete_file(f"/{metadata_filename}")
                return

        raise BackupNotFound(f"Backup {backup_id} not found")
