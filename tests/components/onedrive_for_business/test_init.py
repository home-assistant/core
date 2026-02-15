"""Test the OneDrive setup."""

from copy import copy
from unittest.mock import MagicMock

from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import AppRoot, Folder
import pytest

from homeassistant.components.onedrive_for_business.const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_PATH,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

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
    mock_onedrive_client.get_drive_item.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_get_integration_folder_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    mock_approot: AppRoot,
    mock_folder: Folder,
) -> None:
    """Test faulty integration folder creation."""
    folder_name = copy(mock_config_entry.data[CONF_FOLDER_PATH])
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_onedrive_client.create_folder.assert_called_once_with(
        parent_id="root",
        name=folder_name,
    )
    # ensure the folder id and name are updated
    assert mock_config_entry.data[CONF_FOLDER_ID] == mock_folder.id
    assert mock_config_entry.data[CONF_FOLDER_PATH] == folder_name


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
    assert "Failed to get backups/home_assistant folder" in caplog.text
