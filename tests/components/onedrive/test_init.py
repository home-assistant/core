"""Test the OneDrive setup."""

from copy import deepcopy
from html import escape
from json import dumps
from unittest.mock import MagicMock

from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)
import pytest

from homeassistant.components.onedrive.const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import BACKUP_METADATA, MOCK_APPROOT, MOCK_BACKUP_FILE, MOCK_BACKUP_FOLDER

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client_init: MagicMock,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    # Ensure the token callback is set up correctly
    token_callback = mock_onedrive_client_init.call_args[0][0]
    assert await token_callback() == "mock-access-token"

    # make sure metadata migration is not called
    assert mock_onedrive_client.upload_file.call_count == 0
    assert mock_onedrive_client.update_drive_item.call_count == 0

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        (AuthenticationError(403, "Auth failed"), ConfigEntryState.SETUP_ERROR),
        (OneDriveException(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_approot_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test errors during approot retrieval."""
    mock_onedrive_client.get_approot.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_get_integration_folder_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test faulty integration folder retrieval."""
    mock_onedrive_client.get_drive_item.side_effect = OneDriveException()
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Failed to get backups_123 folder" in caplog.text


async def test_get_integration_folder_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test faulty integration folder creation."""
    folder_name = deepcopy(mock_config_entry.data[CONF_FOLDER_NAME])
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_onedrive_client.create_folder.assert_called_once_with(
        parent_id=MOCK_APPROOT.id,
        name=folder_name,
    )
    # ensure the folder id and name are updated
    assert mock_config_entry.data[CONF_FOLDER_ID] == MOCK_BACKUP_FOLDER.id
    assert mock_config_entry.data[CONF_FOLDER_NAME] == MOCK_BACKUP_FOLDER.name


async def test_get_integration_folder_creation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test faulty integration folder creation error."""
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    mock_onedrive_client.create_folder.side_effect = OneDriveException()
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Failed to get backups_123 folder" in caplog.text


async def test_migrate_metadata_files(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test migration of metadata files."""
    MOCK_BACKUP_FILE.description = escape(
        dumps({**BACKUP_METADATA, "metadata_version": 1})
    )
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    mock_onedrive_client.upload_file.assert_called_once()
    assert mock_onedrive_client.update_drive_item.call_count == 3
    assert mock_onedrive_client.update_drive_item.call_args[1]["data"].description == ""


async def test_migrate_metadata_files_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test migration of metadata files errors."""
    mock_onedrive_client.list_drive_items.side_effect = OneDriveException()
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_error_during_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test auth error during update."""
    mock_onedrive_client.get_drive.side_effect = AuthenticationError(403, "Auth failed")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_1_1_to_1_2_migration(
    hass: HomeAssistant,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from 1.1 to 1.2."""
    old_config_entry = MockConfigEntry(
        unique_id="mock_drive_id",
        title="John Doe's OneDrive",
        domain=DOMAIN,
        data={
            "auth_implementation": mock_config_entry.data["auth_implementation"],
            "token": mock_config_entry.data["token"],
        },
    )

    # will always 404 after migration, because of dummy id
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")

    await setup_integration(hass, old_config_entry)
    assert old_config_entry.data[CONF_FOLDER_ID] == MOCK_BACKUP_FOLDER.id
    assert old_config_entry.data[CONF_FOLDER_NAME] == MOCK_BACKUP_FOLDER.name


async def test_migration_guard_against_major_downgrade(
    hass: HomeAssistant,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration guards against major downgrades."""
    old_config_entry = MockConfigEntry(
        unique_id="mock_drive_id",
        title="John Doe's OneDrive",
        domain=DOMAIN,
        data={
            "auth_implementation": mock_config_entry.data["auth_implementation"],
            "token": mock_config_entry.data["token"],
        },
        version=2,
    )

    await setup_integration(hass, old_config_entry)
    assert old_config_entry.state == ConfigEntryState.MIGRATION_ERROR
