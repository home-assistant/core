"""API for Dropbox bound to Home Assistant OAuth."""

from collections.abc import AsyncIterator, Callable, Coroutine
import json
from typing import Any

from python_dropbox_api import (
    AccountInfo,
    Auth,
    DropboxAPIClient,
    DropboxAuthException,
    DropboxFileOrFolderNotFoundException,
    DropboxUnknownException,
    PropertyField,
    PropertyFieldValue,
    PropertyGroup,
    PropertyTemplate,
)

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)

FOLDER_PATH = "/Home Assistant"

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

    async def _async_ensure_folder_exists(self) -> None:
        """Ensure the folder exists."""
        try:
            metadata = await self._api.get_metadata(FOLDER_PATH)
        except DropboxFileOrFolderNotFoundException:
            try:
                await self._api.create_folder(FOLDER_PATH)
            except (
                DropboxAuthException,
                DropboxFileOrFolderNotFoundException,
                DropboxUnknownException,
            ) as ex:
                raise BackupAgentError(
                    f"Failed to create folder 'Home Assistant' in Dropbox: {ex}"
                ) from ex
            return

        if not metadata.is_folder:
            raise BackupAgentError(
                "The path 'Home Assistant' exists as a file in Dropbox, but a folder is required."
            )

    async def _async_get_backups(self) -> list[tuple[AgentBackup, str]]:
        """Get backups and their corresponding file names."""
        property_template_id = await self.async_get_property_template_id()

        files = await self._api.list_folder(
            FOLDER_PATH, include_property_groups=[property_template_id]
        )

        backups: list[tuple[AgentBackup, str]] = []
        for file in files:
            if file.property_groups is not None:
                for property_group in file.property_groups:
                    if property_group.template_id == property_template_id:
                        backups.append(
                            (
                                AgentBackup.from_dict(
                                    json.loads(property_group.fields[0].value)
                                ),
                                file.name,
                            )
                        )
                        break  # Found matching template, no need to check other groups

        return backups

    async def async_list_backups(self) -> list[AgentBackup]:
        """List backups."""
        await self._async_ensure_folder_exists()

        return [backup for backup, _ in await self._async_get_backups()]

    async def async_upload_backup(
        self,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
    ) -> None:
        """Upload a backup."""
        await self._async_ensure_folder_exists()

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
            f"{FOLDER_PATH}/{filename}", file_stream, [property_group]
        )

    async def async_download_backup(self, backup_id: str) -> AsyncIterator[bytes]:
        """Download a backup."""
        await self._async_ensure_folder_exists()

        backups = await self._async_get_backups()
        for backup, filename in backups:
            if backup.backup_id == backup_id:
                return self._api.download_file(f"{FOLDER_PATH}/{filename}")

        raise BackupNotFound(f"Backup {backup_id} not found")

    async def async_delete_backup(self, backup_id: str) -> None:
        """Delete a backup."""
        await self._async_ensure_folder_exists()

        backups = await self._async_get_backups()
        for backup, filename in backups:
            if backup.backup_id == backup_id:
                await self._api.delete_file(f"{FOLDER_PATH}/{filename}")
                return

        raise BackupNotFound(f"Backup {backup_id} not found")
