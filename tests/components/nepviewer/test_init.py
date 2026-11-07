"""Test the NEPViewer integration setup."""

from unittest.mock import MagicMock

from aionepviewer import NepAuthError, NepConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
) -> None:
    """Test a successful integration setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
) -> None:
    """Test that a config entry can be unloaded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            NepAuthError,
            ConfigEntryState.SETUP_ERROR,
            id="auth_failure_setup_error",
        ),
        pytest.param(
            NepConnectionError,
            ConfigEntryState.SETUP_RETRY,
            id="connection_error_setup_retry",
        ),
    ],
)
async def test_setup_entry_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    side_effect: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test that setup fails gracefully on API errors."""
    mock_nepviewer.get_sites.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
