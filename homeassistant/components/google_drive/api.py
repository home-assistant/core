"""API for Google Drive bound to Home Assistant OAuth."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
import json
import logging
from typing import Any

from aiohttp import ClientSession, ClientTimeout, StreamReader
from aiohttp.client_exceptions import ClientError, ClientResponseError
from google_drive_api.api import AbstractAuth, GoogleDriveApi

from homeassistant.components.backup import AgentBackup, suggested_filename
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_entry_oauth2_flow

_UPLOAD_AND_DOWNLOAD_TIMEOUT = 12 * 3600

_LOGGER = logging.getLogger(__name__)


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

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        try:
            await self._oauth_session.async_ensure_token_valid()
        except ClientError as ex:
            if (
                self._oauth_session.config_entry.state
                is ConfigEntryState.SETUP_IN_PROGRESS
            ):
                if isinstance(ex, ClientResponseError) and 400 <= ex.status < 500:
                    raise ConfigEntryAuthFailed(
                        "OAuth session is not valid, reauth required"
                    ) from ex
                raise ConfigEntryNotReady from ex
            if hasattr(ex, "status") and ex.status == 400:
                self._oauth_session.config_entry.async_start_reauth(
                    self._oauth_session.hass
                )
            raise HomeAssistantError(ex) from ex
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

    async def async_create_ha_root_folder_if_not_exists(self) -> tuple[str, str]:
        """Create Home Assistant folder if it doesn't exist."""
        fields = "id,name"
        query = " and ".join(
            [
                "properties has { key='home_assistant' and value='root' }",
                f"properties has {{ key='instance_id' and value='{self._ha_instance_id}' }}",
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
            timeout=ClientTimeout(total=_UPLOAD_AND_DOWNLOAD_TIMEOUT),
        )
        _LOGGER.debug(
            "Uploaded backup: %s to: '%s'",
            backup.backup_id,
            backup_metadata["name"],
        )

    async def async_list_backups(self) -> list[AgentBackup]:
        """List backups."""
        query = " and ".join(
            [
                "properties has { key='home_assistant' and value='backup' }",
                f"properties has {{ key='instance_id' and value='{self._ha_instance_id}' }}",
                "trashed=false",
            ]
        )
        res = await self._api.list_files(
            params={"q": query, "fields": "files(description)"}
        )
        backups = []
        for file in res["files"]:
            backup = AgentBackup.from_dict(json.loads(file["description"]))
            backups.append(backup)
        return backups

    async def async_get_backup_file_id(self, backup_id: str) -> str | None:
        """Get file_id of backup if it exists."""
        query = " and ".join(
            [
                "properties has { key='home_assistant' and value='backup' }",
                f"properties has {{ key='instance_id' and value='{self._ha_instance_id}' }}",
                f"properties has {{ key='backup_id' and value='{backup_id}' }}",
            ]
        )
        res = await self._api.list_files(params={"q": query, "fields": "files(id)"})
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
