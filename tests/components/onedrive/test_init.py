"""Test the OneDrive setup."""

from copy import copy
from html import escape
from json import dumps
from unittest.mock import MagicMock

from onedrive_personal_sdk.const import DriveState
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import AppRoot, Drive, File, Folder, ItemUpdate
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.onedrive.const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from . import setup_integration
from .const import BACKUP_METADATA, INSTANCE_ID

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
    mock_approot: AppRoot,
    mock_folder: Folder,
) -> None:
    """Test faulty integration folder creation."""
    folder_name = copy(mock_config_entry.data[CONF_FOLDER_NAME])
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_onedrive_client.create_folder.assert_called_once_with(
        parent_id=mock_approot.id,
        name=folder_name,
    )
    # ensure the folder id and name are updated
    assert mock_config_entry.data[CONF_FOLDER_ID] == mock_folder.id
    assert mock_config_entry.data[CONF_FOLDER_NAME] == mock_folder.name


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


async def test_update_instance_id_description(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    mock_folder: Folder,
) -> None:
    """Test we write the instance id to the folder."""
    mock_folder.description = ""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    mock_onedrive_client.update_drive_item.assert_called_with(
        mock_folder.id, ItemUpdate(description=INSTANCE_ID)
    )


async def test_migrate_metadata_files(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    mock_backup_file: File,
) -> None:
    """Test migration of metadata files."""
    mock_backup_file.description = escape(
        dumps({**BACKUP_METADATA, "metadata_version": 1})
    )
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    mock_onedrive_client.upload_file.assert_called_once()
    assert mock_onedrive_client.update_drive_item.call_count == 2
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


async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_drive: Drive,
) -> None:
    """Test the device."""

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device({(DOMAIN, mock_drive.id)})
    assert device
    assert device == snapshot


@pytest.mark.parametrize(
    (
        "drive_state",
        "issue_key",
        "issue_exists",
    ),
    [
        (DriveState.NORMAL, "drive_full", False),
        (DriveState.NORMAL, "drive_almost_full", False),
        (DriveState.CRITICAL, "drive_almost_full", True),
        (DriveState.CRITICAL, "drive_full", False),
        (DriveState.EXCEEDED, "drive_almost_full", False),
        (DriveState.EXCEEDED, "drive_full", True),
    ],
)
async def test_data_cap_issues(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    mock_drive: Drive,
    drive_state: DriveState,
    issue_key: str,
    issue_exists: bool,
) -> None:
    """Make sure we get issues for high data usage."""
    assert mock_drive.quota
    mock_drive.quota.state = drive_state

    await setup_integration(hass, mock_config_entry)

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, issue_key)
    assert (issue is not None) == issue_exists


async def test_1_1_to_1_2_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_folder: Folder,
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

    await setup_integration(hass, old_config_entry)
    assert old_config_entry.data[CONF_FOLDER_ID] == mock_folder.id
    assert old_config_entry.data[CONF_FOLDER_NAME] == mock_folder.name
    assert old_config_entry.minor_version == 2


async def test_1_1_to_1_2_migration_failure(
    hass: HomeAssistant,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from 1.1 to 1.2 failure."""
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
    assert old_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert old_config_entry.minor_version == 1


async def test_migration_guard_against_major_downgrade(
    hass: HomeAssistant,
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
    assert old_config_entry.state is ConfigEntryState.MIGRATION_ERROR
