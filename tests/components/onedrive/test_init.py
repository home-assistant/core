"""Test the OneDrive setup."""

from html import escape
from json import dumps
from unittest.mock import MagicMock

from onedrive_personal_sdk.exceptions import AuthenticationError, OneDriveException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import BACKUP_METADATA, MOCK_BACKUP_FILE

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
    """Test faulty approot retrieval."""
    mock_onedrive_client.create_folder.side_effect = OneDriveException()
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Failed to get backups_9f86d081 folder" in caplog.text


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
