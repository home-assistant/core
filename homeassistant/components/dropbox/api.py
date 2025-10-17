"""API for Dropbox bound to Home Assistant OAuth."""

from collections.abc import AsyncIterator, Callable, Coroutine
import json
from typing import Any

from aiohttp import ClientSession
from python_dropbox_api import (
    AccountInfo,
    Auth,
    DropboxAPIClient,
    DropboxFileOrFolderNotFoundException,
    PropertyField,
    PropertyFieldValue,
    PropertyGroup,
    PropertyTemplate,
)

from homeassistant.components.backup.models import AgentBackup, BackupNotFound
from homeassistant.components.backup.util import suggested_filename
from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(Auth):
    """Provide Dropbox authentication tied to an OAuth2 based config entry."""

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
        await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]


class AsyncConfigFlowAuth(Auth):
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
        """Return the fixed access token."""
        return self._token


FOLDER_NAME = "Home Assistant"

PROPERTY_TEMPLATE_NAME = "Home Assistant Backups"
PROPERTY_TEMPLATE_DESCRIPTION = "Metadata about a Home Assistant backup."
PROPERTY_FIELD_NAME = "Metadata"
PROPERTY_FIELD_DESCRIPTION = (
    "Metadata about the Home Assistant backup formatted as a JSON string."
)


class DropboxClient:
    """Dropbox client."""

    _property_template_id: str | None = None

    def __init__(self, auth: Auth) -> None:
        """Initialize Dropbox client."""
        self._api = DropboxAPIClient(auth)

    async def async_get_account_info(self) -> AccountInfo:
        """Get information about the current account."""
        return await self._api.get_account_info()

    async def async_get_property_template_id(self) -> str:
        """Get the ID of the property template for Home Assistant backups."""

        if self._property_template_id is not None:
            return self._property_template_id

        template_ids = await self._api.list_property_templates()

        for template_id in template_ids:
            template = await self._api.get_property_template(template_id)
            if template.name == PROPERTY_TEMPLATE_NAME:
                return template_id

        # Couldn't find a matching property template, so create a new one
        property_template = PropertyTemplate(
            name=PROPERTY_TEMPLATE_NAME,
            description=PROPERTY_TEMPLATE_DESCRIPTION,
            fields=[
                PropertyField(
                    name=PROPERTY_FIELD_NAME,
                    description=PROPERTY_FIELD_DESCRIPTION,
                    type="string",
                )
            ],
        )

        new_template_id = await self._api.add_property_template(property_template)
        self._property_template_id = new_template_id
        return new_template_id

    async def async_ensure_folder_exists(self) -> None:
        """Ensure the folder exists."""
        try:
            metadata = await self._api.get_metadata(f"/{FOLDER_NAME}")
        except DropboxFileOrFolderNotFoundException:
            await self._api.create_folder(f"/{FOLDER_NAME}")
            return

        if not metadata.is_folder:
            # TODO: throw correct error
            raise ValueError("Home Assistant exists as a file, not a folder")

    async def async_list_backups(self) -> list[AgentBackup]:
        """List backups."""
        await self.async_ensure_folder_exists()

        property_template_id = await self.async_get_property_template_id()

        files = await self._api.list_folder(
            f"/{FOLDER_NAME}", include_property_groups=[property_template_id]
        )

        backups: list[AgentBackup] = []
        for file in files:
            if file.property_groups is not None:
                # Check if any property group matches the template_id
                for property_group in file.property_groups:
                    if property_group.template_id == property_template_id:
                        backups.append(
                            AgentBackup.from_dict(
                                json.loads(property_group.fields[0].value)
                            )
                        )
                        break  # Found matching template, no need to check other groups

        return backups

    async def async_upload_backup(
        self,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        """Upload a backup."""
        await self.async_ensure_folder_exists()

        property_template_id = await self.async_get_property_template_id()

        property_group = PropertyGroup(
            template_id=property_template_id,
            fields=[
                PropertyFieldValue(
                    name=PROPERTY_FIELD_NAME, value=json.dumps(backup.as_dict())
                ),
            ],
        )

        filename = suggested_filename(backup)

        file_stream = await open_stream()

        await self._api.upload_file(
            f"/{FOLDER_NAME}/{filename}", file_stream, [property_group]
        )

    async def async_download_backup(self, backup_id: str) -> AsyncIterator[bytes]:
        """Download a backup."""
        await self.async_ensure_folder_exists()

        property_template_id = await self.async_get_property_template_id()

        files = await self._api.list_folder(
            f"/{FOLDER_NAME}", include_property_groups=[property_template_id]
        )

        for file in files:
            if file.property_groups is not None:
                for property_group in file.property_groups:
                    if property_group.template_id == property_template_id:
                        backup = AgentBackup.from_dict(
                            json.loads(property_group.fields[0].value)
                        )
                        if backup.backup_id == backup_id:
                            return self._api.download_file(
                                f"/{FOLDER_NAME}/{file.name}"
                            )

        raise BackupNotFound(f"Backup {backup_id} not found")

    async def async_delete_backup(self, backup_id: str) -> None:
        """Delete a backup."""
        await self.async_ensure_folder_exists()

        property_template_id = await self.async_get_property_template_id()

        files = await self._api.list_folder(
            f"/{FOLDER_NAME}", include_property_groups=[property_template_id]
        )

        for file in files:
            if file.property_groups is not None:
                for property_group in file.property_groups:
                    if property_group.template_id == property_template_id:
                        backup = AgentBackup.from_dict(
                            json.loads(property_group.fields[0].value)
                        )
                        if backup.backup_id == backup_id:
                            await self._api.delete_file(f"/{FOLDER_NAME}/{file.name}")
                            return

        raise BackupNotFound(f"Backup {backup_id} not found")
