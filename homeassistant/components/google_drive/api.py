"""API for Google Drive bound to Home Assistant OAuth."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
import json
import logging
from typing import Any

from aiohttp import ClientSession, ClientTimeout, MultipartWriter, StreamReader
from aiohttp.client_exceptions import ClientError, ClientResponseError
from google.auth.exceptions import RefreshError

from homeassistant.components.backup import AgentBackup
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_entry_oauth2_flow

DRIVE_API_ABOUT = "https://www.googleapis.com/drive/v3/about"
DRIVE_API_FILES = "https://www.googleapis.com/drive/v3/files"
DRIVE_API_UPLOAD_FILES = "https://www.googleapis.com/upload/drive/v3/files"
_UPLOAD_TIMEOUT = 12 * 3600

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth:
    """Provide Google Drive authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Google Drive Auth."""
        self._hass = hass
        self.oauth_session = oauth2_session

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return str(self.oauth_session.token[CONF_ACCESS_TOKEN])

    async def check_and_refresh_token(self) -> str:
        """Check the token."""
        try:
            await self.oauth_session.async_ensure_token_valid()
        except (RefreshError, ClientResponseError, ClientError) as ex:
            if (
                self.oauth_session.config_entry.state
                is ConfigEntryState.SETUP_IN_PROGRESS
            ):
                if isinstance(ex, ClientResponseError) and 400 <= ex.status < 500:
                    raise ConfigEntryAuthFailed(
                        "OAuth session is not valid, reauth required"
                    ) from ex
                raise ConfigEntryNotReady from ex
            if (
                isinstance(ex, RefreshError)
                or hasattr(ex, "status")
                and ex.status == 400
            ):
                self.oauth_session.config_entry.async_start_reauth(
                    self.oauth_session.hass
                )
            raise HomeAssistantError(ex) from ex
        return self.access_token


class DriveClient:
    """Google Drive client."""

    def __init__(
        self,
        session: ClientSession,
        ha_instance_id: str,
        access_token: str | None,
        auth: AsyncConfigEntryAuth | None,
    ) -> None:
        """Initialize Google Drive client."""
        self._session = session
        self._ha_instance_id = ha_instance_id
        self._access_token = access_token
        self._auth = auth
        assert self._access_token or self._auth

    async def _async_get_headers(self) -> dict[str, str]:
        if self._access_token:
            access_token = self._access_token
        else:
            assert self._auth
            access_token = await self._auth.check_and_refresh_token()
        return {"Authorization": f"Bearer {access_token}"}

    async def async_get_email_address(self) -> str:
        """Get email address of the current user."""
        headers = await self._async_get_headers()
        resp = await self._session.get(
            DRIVE_API_ABOUT,
            params={"fields": "user(emailAddress)"},
            headers=headers,
        )
        resp.raise_for_status()
        res = await resp.json()
        return str(res["user"]["emailAddress"])

    async def async_create_ha_root_folder_if_not_exists(self) -> tuple[str, str]:
        """Create Home Assistant folder if it doesn't exist."""
        fields = "id,name"
        query = " and ".join(
            [
                "properties has { key='ha' and value='root' }",
                f"properties has {{ key='instance_id' and value='{self._ha_instance_id}' }}",
            ]
        )
        res = await self.async_query(query, f"files({fields})")
        for file in res["files"]:
            _LOGGER.debug("Found existing folder: %s", file)
            return str(file["id"]), str(file["name"])

        headers = await self._async_get_headers()
        file_metadata = {
            "name": "Home Assistant",
            "mimeType": "application/vnd.google-apps.folder",
            "properties": {
                "ha": "root",
                "instance_id": self._ha_instance_id,
            },
        }
        _LOGGER.debug("Creating new folder with metadata: %s", file_metadata)
        resp = await self._session.post(
            DRIVE_API_FILES,
            params={"fields": fields},
            json=file_metadata,
            headers=headers,
        )
        resp.raise_for_status()
        res = await resp.json()
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
            "name": f"{backup.name} {backup.date}.tar",
            "description": json.dumps(backup.as_dict()),
            "parents": [folder_id],
            "properties": {
                "ha": "backup",
                "instance_id": self._ha_instance_id,
                "backup_id": backup.backup_id,
            },
        }
        _LOGGER.debug(
            "Uploading backup: %s with Google Drive metadata: %s",
            backup.backup_id,
            backup_metadata,
        )
        await self.async_upload(backup_metadata, open_stream)
        _LOGGER.debug(
            "Uploaded backup: %s to: '%s'",
            backup.backup_id,
            backup_metadata["name"],
        )

    async def async_list_backups(self) -> list[AgentBackup]:
        """List backups."""
        query = " and ".join(
            [
                "properties has { key='ha' and value='backup' }",
                f"properties has {{ key='instance_id' and value='{self._ha_instance_id}' }}",
                "trashed=false",
            ]
        )
        res = await self.async_query(query, "files(description)")
        backups = []
        for file in res["files"]:
            backup = AgentBackup.from_dict(json.loads(file["description"]))
            backups.append(backup)
        return backups

    async def async_get_backup_file_id(self, backup_id: str) -> str | None:
        """Get file_id of backup if it exists."""
        query = " and ".join(
            [
                "properties has { key='ha' and value='backup' }",
                f"properties has {{ key='instance_id' and value='{self._ha_instance_id}' }}",
                f"properties has {{ key='backup_id' and value='{backup_id}' }}",
            ]
        )
        res = await self.async_query(query, "files(id)")
        for file in res["files"]:
            return str(file["id"])
        return None

    async def async_delete(self, file_id: str) -> None:
        """Delete file."""
        headers = await self._async_get_headers()
        resp = await self._session.delete(
            f"{DRIVE_API_FILES}/{file_id}", headers=headers
        )
        resp.raise_for_status()

    async def async_download(self, file_id: str) -> StreamReader:
        """Download a file."""
        headers = await self._async_get_headers()
        resp = await self._session.get(
            f"{DRIVE_API_FILES}/{file_id}",
            params={"alt": "media"},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.content

    async def async_upload(
        self,
        file_metadata: dict[str, Any],
        open_stream: Callable[
            [], Coroutine[Any, Any, AsyncIterator[bytes]] | Awaitable[bytes]
        ],
    ) -> None:
        """Upload a file."""
        headers = await self._async_get_headers()
        with MultipartWriter() as mpwriter:
            mpwriter.append_json(file_metadata)
            mpwriter.append(await open_stream())
            headers.update(
                {"Content-Type": f"multipart/related; boundary={mpwriter.boundary}"}
            )
            resp = await self._session.post(
                DRIVE_API_UPLOAD_FILES,
                params={"fields": ""},
                data=mpwriter,
                headers=headers,
                timeout=ClientTimeout(total=_UPLOAD_TIMEOUT),
            )
            resp.raise_for_status()

    async def async_query(
        self,
        query: str,
        fields: str,
    ) -> dict[str, Any]:
        """Query for files."""
        headers = await self._async_get_headers()
        _LOGGER.debug("async_query: query: '%s' fields: '%s'", query, fields)
        resp = await self._session.get(
            DRIVE_API_FILES,
            params={"q": query, "fields": fields},
            headers=headers,
        )
        resp.raise_for_status()
        res: dict[str, Any] = await resp.json()
        _LOGGER.debug("async_query result: %s", res)
        return res
