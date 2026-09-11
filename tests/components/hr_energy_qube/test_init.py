"""Test the Qube Heat Pump integration init."""

from unittest.mock import MagicMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_qube_client.close.assert_called_once()


@pytest.mark.parametrize(
    ("connect_result", "connect_error"),
    [
        (False, None),
        (None, OSError("Connection refused")),
    ],
)
async def test_setup_entry_connection_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    connect_result: bool | None,
    connect_error: Exception | None,
) -> None:
    """Test setup failure when the device cannot be reached."""
    if connect_error is not None:
        mock_qube_client.connect.side_effect = connect_error
    else:
        mock_qube_client.connect.return_value = connect_result

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_qube_client.close.assert_called_once()
