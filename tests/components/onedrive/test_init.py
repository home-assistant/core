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
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    # Ensure the token callback is set up correctly
    token_callback = mock_onedrive_client_init.call_args[0][0]
    assert await token_callback() == "mock-access-token"

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


async def test_v1_v2_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test migration from v1 to v2."""
    MOCK_BACKUP_FILE.description = escape(
        dumps({**BACKUP_METADATA, "metadata_version": 1})
    )
    v1_config_entry = MockConfigEntry(
        data=mock_config_entry.data,
        version=1,
        title=mock_config_entry.title,
        domain=mock_config_entry.domain,
        unique_id=mock_config_entry.unique_id,
    )
    await setup_integration(hass, v1_config_entry)
    await hass.async_block_till_done()

    mock_onedrive_client.upload_file.assert_called_once()
    assert mock_onedrive_client.update_drive_item.call_count == 2
    assert mock_onedrive_client.update_drive_item.call_args[1]["data"].description == ""
    assert v1_config_entry.version == 2


async def test_v1_v2_migration_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    mock_onedrive_client_init: MagicMock,
) -> None:
    """Test errors during v1 to v2 migration."""
    v1_config_entry = MockConfigEntry(
        data=mock_config_entry.data,
        version=1,
        title=mock_config_entry.title,
        domain=mock_config_entry.domain,
        unique_id=mock_config_entry.unique_id,
    )
    mock_onedrive_client.list_drive_items.side_effect = OneDriveException()
    await setup_integration(hass, v1_config_entry)

    # Ensure the token callback is set up correctly
    token_callback = mock_onedrive_client_init.call_args[0][0]
    assert await token_callback() == "mock-access-token"

    assert v1_config_entry.state is ConfigEntryState.MIGRATION_ERROR
