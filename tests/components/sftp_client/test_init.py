"""Test the SFTPClient setup."""

from homeassistant.components.sftp_client.helpers import BackupFolderError, InvalidAuth
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import AsyncMock, MockConfigEntry


async def test_load_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sftp_client: AsyncMock,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sftp_client: AsyncMock,
) -> None:
    """Test invalid authentication."""
    sftp_client.async_connect.side_effect = InvalidAuth("Invalid username or password")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_create_folder_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sftp_client: AsyncMock,
) -> None:
    """Test create folder error."""
    sftp_client.async_create_backup_path.side_effect = BackupFolderError(
        "Failed to create backup folder"
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_create_folder_not_exists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sftp_client: AsyncMock,
) -> None:
    """Test folder backup not exists."""
    sftp_client.async_ensure_path_exists.return_value = False
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
