"""Test the OneDrive setup."""

from unittest.mock import MagicMock

from kiota_abstractions.api_error import APIError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_graph_client: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    (
        "side_effect",
        "state",
    ),
    [
        (APIError(response_status_code=403), ConfigEntryState.SETUP_ERROR),
        (APIError(response_status_code=500), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_approot_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_graph_client: MagicMock,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test errors during approot retrieval."""
    mock_graph_client.drives.by_drive_id.return_value.special.by_drive_item_id.return_value.get.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_faulty_approot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_graph_client: MagicMock,
) -> None:
    """Test faulty approot retrieval."""
    mock_graph_client.drives.by_drive_id.return_value.special.by_drive_item_id.return_value.get.return_value = None
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_faulty_integration_folder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_graph_client: MagicMock,
) -> None:
    """Test faulty approot retrieval."""
    mock_graph_client.drives.by_drive_id.return_value.items.by_drive_item_id.return_value.get.return_value = None
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_backup_folder_did_not_exist(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_graph_client: MagicMock,
) -> None:
    """Test backup folder did not exist."""
    mock_graph_client.drives.by_drive_id.return_value.items.by_drive_item_id.return_value.get.side_effect = APIError(
        response_status_code=404
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_error_during_backup_folder_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_graph_client: MagicMock,
) -> None:
    """Test error during backup folder creation."""
    mock_graph_client.drives.by_drive_id.return_value.items.by_drive_item_id.return_value.get.side_effect = APIError(
        response_status_code=404
    )
    mock_graph_client.drives.by_drive_id.return_value.items.by_drive_item_id.return_value.children.post.side_effect = APIError()
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
