"""API for Google Drive bound to Home Assistant OAuth."""

from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
import json
import logging
from typing import Any, override

from aiohttp import ClientSession, ClientTimeout, StreamReader
from aiohttp.client_exceptions import ClientError, ClientResponseError
from google_drive_api.api import AbstractAuth, GoogleDriveApi

from homeassistant.components.backup import AgentBackup, suggested_filename
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_UPLOAD_AND_DOWNLOAD_TIMEOUT = 12 * 3600
_UPLOAD_MAX_RETRIES = 20

_LOGGER = logging.getLogger(__name__)


@dataclass
class StorageQuotaData:
    """Class to represent storage quota data."""

    limit: int | None
    usage: int
    usage_in_drive: int
    usage_in_trash: int


def _parse_backup_metadata(file: dict[str, Any]) -> AgentBackup | None:
    """Return the backup a Drive file describes, or None if it cannot be read.

    The metadata lives in the file description, which the user can edit or clear
    from the Google Drive UI. One unreadable file should not hide the others.
    """
    reason: object
    try:
        backup = AgentBackup.from_dict(json.loads(file["description"]))
    except (KeyError, TypeError, ValueError) as err:
        reason = err
    else:
        # from_dict does not enforce its annotations, so metadata that decodes
        # but holds the wrong types still has to be rejected here. The backup
        # manager uses backup_id as a dict key and calls extra_metadata.get()
        # on every backup it lists.
        if not isinstance(backup.backup_id, str):
            reason = "backup_id is not a string"
        elif not isinstance(backup.extra_metadata, dict):
            reason = "extra_metadata is not a dictionary"
        else:
            return backup
    _LOGGER.warning(
        "Ignoring backup file %s: its description is not valid backup metadata: %s",
        file.get("id", "?"),
        reason,
    )
    return None


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Google Drive authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize AsyncConfigEntryAuth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        try:
            await self._oauth_session.async_ensure_token_valid()
        except ClientError as ex:
            is_setup = (
                self._oauth_session.config_entry.state
                is ConfigEntryState.SETUP_IN_PROGRESS
            )

            if isinstance(ex, ClientResponseError):
                # OAuth2 spec uses 400 for invalid refresh tokens.
                # During setup, we broaden this to all 4xx to abort cleanly.
                if ex.status == 400 or (is_setup and 400 <= ex.status < 500):
                    if not is_setup:
                        self._oauth_session.config_entry.async_start_reauth(
                            self._oauth_session.hass
                        )
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="authentication_not_valid",
                    ) from ex

            if is_setup:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from ex

            raise

        return str(self._oauth_session.token[CONF_ACCESS_TOKEN])


class AsyncConfigFlowAuth(AbstractAuth):
    """Provide authentication tied to a fixed token for the config flow."""

    def __init__(
        self,
        websession: ClientSession,
        token: str,
    ) -> None:
        """Initialize AsyncConfigFlowAuth."""
        super().__init__(websession)
        self._token = token

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self._token


class DriveClient:
    """Google Drive client."""

    def __init__(
        self,
        ha_instance_id: str,
        auth: AbstractAuth,
    ) -> None:
        """Initialize Google Drive client."""
        self._ha_instance_id = ha_instance_id
        self._api = GoogleDriveApi(auth)

    async def async_get_email_address(self) -> str:
        """Get email address of the current user."""
        res = await self._api.get_user(params={"fields": "user(emailAddress)"})
        return str(res["user"]["emailAddress"])

    async def async_get_storage_quota(self) -> StorageQuotaData:
        """Get storage quota of the current user."""
        res = await self._api.get_user(params={"fields": "storageQuota"})

        storage_quota = res["storageQuota"]
        limit = storage_quota.get("limit")
        return StorageQuotaData(
            limit=int(limit) if limit is not None else None,
            usage=int(storage_quota.get("usage", 0)),
            usage_in_drive=int(storage_quota.get("usageInDrive", 0)),
            usage_in_trash=int(storage_quota.get("usageInTrash", 0)),
        )

    async def async_create_ha_root_folder_if_not_exists(self) -> tuple[str, str]:
        """Create Home Assistant folder if it doesn't exist."""
        fields = "id,name"
        query = " and ".join(
            [
                "properties has { key='home_assistant' and value='root' }",
                "properties has { key='instance_id'"
                f" and value='{self._ha_instance_id}' }}",
                "trashed=false",
            ]
        )
        res = await self._api.list_files(
            params={"q": query, "fields": f"files({fields})"}
        )
        for file in res["files"]:
            _LOGGER.debug("Found existing folder: %s", file)
            return str(file["id"]), str(file["name"])

        file_metadata = {
            "name": "Home Assistant",
            "mimeType": "application/vnd.google-apps.folder",
            "properties": {
                "home_assistant": "root",
                "instance_id": self._ha_instance_id,
            },
        }
        _LOGGER.debug("Creating new folder with metadata: %s", file_metadata)
        res = await self._api.create_file(params={"fields": fields}, json=file_metadata)
        _LOGGER.debug("Created folder: %s", res)
        return str(res["id"]), str(res["name"])

    async def async_upload_backup(
        self,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        """Upload a backup."""
        folder_id, _ = await self.async_create_ha_root_folder_if_not_exists()
        backup_metadata = {
            "name": suggested_filename(backup),
            "description": json.dumps(backup.as_dict()),
            "parents": [folder_id],
            "properties": {
                "home_assistant": "backup",
                "instance_id": self._ha_instance_id,
                "backup_id": backup.backup_id,
            },
        }
        _LOGGER.debug(
            "Uploading backup: %s with Google Drive metadata: %s",
            backup.backup_id,
            backup_metadata,
        )
        await self._api.resumable_upload_file(
            backup_metadata,
            open_stream,
            backup.size,
            max_retries=_UPLOAD_MAX_RETRIES,
            timeout=ClientTimeout(total=_UPLOAD_AND_DOWNLOAD_TIMEOUT),
        )
        _LOGGER.debug(
            "Uploaded backup: %s to: '%s'",
            backup.backup_id,
            backup_metadata["name"],
        )

    def _backup_query(self, *extra: str) -> str:
        """Return a query matching the backups of this Home Assistant instance."""
        return " and ".join(
            [
                "properties has { key='home_assistant' and value='backup' }",
                "properties has { key='instance_id'"
                f" and value='{self._ha_instance_id}' }}",
                "trashed=false",
                *extra,
            ]
        )

    async def async_list_backups(self) -> list[AgentBackup]:
        """List backups."""
        res = await self._api.list_files(
            params={"q": self._backup_query(), "fields": "files(id,description)"}
        )
        return [
            backup
            for file in res["files"]
            if (backup := _parse_backup_metadata(file)) is not None
        ]

    async def async_get_size_of_all_backups(self) -> int:
        """Get size of all backups."""
        # Ask Drive for the size of each file instead of adding up the sizes stored
        # in the metadata, which would mean downloading and parsing every backup's
        # description just to update a sensor.
        res = await self._api.list_files(
            params={"q": self._backup_query(), "fields": "files(size)"}
        )
        return sum(int(file["size"]) for file in res["files"] if "size" in file)

    async def async_get_backup_file_id(self, backup_id: str) -> str | None:
        """Get file_id of backup if it exists."""
        res = await self._api.list_files(
            params={
                "q": self._backup_query(
                    f"properties has {{ key='backup_id' and value='{backup_id}' }}"
                ),
                "fields": "files(id)",
            }
        )
        for file in res["files"]:
            return str(file["id"])
        return None

    async def async_delete(self, file_id: str) -> None:
        """Delete file."""
        await self._api.delete_file(file_id)

    async def async_download(self, file_id: str) -> StreamReader:
        """Download a file."""
        resp = await self._api.get_file_content(
            file_id, timeout=ClientTimeout(total=_UPLOAD_AND_DOWNLOAD_TIMEOUT)
        )
        return resp.content
